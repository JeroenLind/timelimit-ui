"""Plan step E3, browser half: rules table and dialog (FR-300..303, FR-305, UI-006)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from .fakeserver import FakeTimeLimitServer

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(5000)
    return page


def open_rules(page: Page, live: Any, child: str = "Anna") -> Any:
    page.goto(live.url + "/")
    expect(page.locator("#overview-list li")).to_have_count(2)
    page.click(f'#overview-list a:has-text("{child}")')
    expect(page.locator("#child-name")).to_have_text(child)
    page.click("#tab-rules")
    return page.locator('.rule-section[data-category-id="cgames"]')


def fill_days(page: Page, days: list[int]) -> None:
    for n in range(7):
        page.set_checked(f'#rule-form input[name="day"][value="{n}"]', n in days)


def games_rules(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"].rules


def test_the_seeded_rule_is_listed_in_words(page: Page, live_app_factory: Any) -> None:
    games = open_rules(page, live_app_factory())
    expect(games.locator("tbody tr")).to_have_count(1)
    expect(games.locator("tbody tr").first).to_contain_text("Every day · 1 h 00 min")


def test_add_a_rule_monday_to_friday_for_90_minutes(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    games = open_rules(page, live_app_factory())
    games.locator(".add-rule").click()
    expect(page.locator("#rule-dialog")).to_be_visible()
    fill_days(page, [0, 1, 2, 3, 4])
    page.fill("#rule-minutes", "90")
    page.click("#rule-save")
    expect(page.locator("#rule-dialog")).to_be_hidden()
    expect(games.locator("tbody tr")).to_have_count(2)
    expect(games).to_contain_text("Mon–Fri · 1 h 30 min")
    assert any(
        r.day_mask == 31 and r.max_time == 90 * 60000
        for r in games_rules(fake_server).values()
    )


def test_edit_a_rule_keeps_the_others_and_shows_details(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    games = open_rules(page, live_app_factory())
    games.locator(".edit-rule").click()
    expect(page.locator("#rule-minutes")).to_have_value("60")
    page.fill("#rule-minutes", "45")
    page.fill("#rule-start", "08:00")
    page.fill("#rule-end", "20:30")
    page.fill("#rule-session", "30")
    page.fill("#rule-pause", "5")
    page.click("#rule-save")
    expect(page.locator("#rule-dialog")).to_be_hidden()
    row = games.locator("tbody tr").first
    expect(row).to_contain_text("Every day · 45 min")
    expect(row).to_contain_text("08:00–20:30")
    expect(row).to_contain_text("30 min, then 5 min break")
    rule = games_rules(fake_server)["rule01"]
    assert (rule.max_time, rule.start, rule.end) == (45 * 60000, 480, 1230)


def test_delete_asks_for_confirmation(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    games = open_rules(page, live_app_factory())
    games.locator(".delete-rule").click()
    page.click("[data-dialog-cancel]")
    expect(games.locator("tbody tr")).to_have_count(1)
    assert "rule01" in games_rules(fake_server)
    games.locator(".delete-rule").click()
    page.click("[data-dialog-ok]")
    expect(games.locator("tbody tr")).to_have_count(0)
    expect(games).to_contain_text("No rules")
    assert games_rules(fake_server) == {}


@pytest.mark.parametrize(
    ("fill", "field", "message"),
    [
        ({"days": []}, "days", "Choose at least one day."),
        ({"minutes": "1441"}, "minutes", "whole number"),
        ({"minutes": ""}, "minutes", "whole number"),
        ({"start": "18:00", "end": "09:00"}, "end", "must not be before"),
        ({"start": "09:00"}, "end", "both a start and an end"),
        ({"session": "30"}, "pause_minutes", "both a session length"),
    ],
)
def test_invalid_input_shows_a_field_message_and_sends_nothing(
    page: Page,
    live_app_factory: Any,
    fake_server: FakeTimeLimitServer,
    fill: dict[str, Any],
    field: str,
    message: str,
) -> None:
    games = open_rules(page, live_app_factory())
    before = fake_server.world.push_requests
    games.locator(".add-rule").click()
    if "days" in fill:
        fill_days(page, fill["days"])
    for name, value in fill.items():
        if name != "days":
            page.fill(f"#rule-{name}", value)
    page.click("#rule-save")
    error = page.locator(f'[data-error-for="{field}"]')
    expect(error).to_be_visible()
    expect(error).to_contain_text(message)
    expect(page.locator("#rule-dialog")).to_be_visible()
    page.wait_for_timeout(300)
    assert fake_server.world.push_requests == before


def test_a_rejected_change_shows_the_error_and_reverts(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    games = open_rules(page, live_app_factory())
    # someone else deleted the rule meanwhile: the server drops our update
    del games_rules(fake_server)["rule01"]
    games.locator(".edit-rule").click()
    page.fill("#rule-minutes", "10")
    page.click("#rule-save")
    expect(page.locator("#rule-error")).to_contain_text("did not accept the change")
    page.click("#rule-cancel")
    expect(games.locator("tbody tr .edit-rule")).to_have_count(
        0
    )  # flagged as gone, no edit offered
    expect(games.locator("tbody tr").first).to_contain_text("No longer on server")


def test_the_rule_buttons_are_disabled_while_the_server_is_down(
    page: Page, live_app_factory: Any, fake_server: FakeTimeLimitServer
) -> None:
    games = open_rules(page, live_app_factory())
    fake_server.faults.drop_connection = True
    expect(page.locator("#server-banner")).to_be_visible(timeout=15000)
    expect(games.locator(".add-rule")).to_be_disabled()
    expect(games.locator(".edit-rule")).to_be_disabled()
    expect(games.locator(".delete-rule")).to_be_disabled()
