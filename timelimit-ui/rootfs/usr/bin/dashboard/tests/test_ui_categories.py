"""Plan step E6a, browser half: the Categories tab (FR-400, FR-401)."""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


@pytest.fixture
def page(browser: Any) -> Any:
    page = browser.new_context(locale="en-US").new_page()
    page.set_default_timeout(8000)
    return page


def family(fake: Any) -> Any:
    return next(iter(fake.world.families.values()))


def open_categories(page: Page, live: Any) -> None:
    page.goto(live.url + "/")
    page.click('#overview-list a:has-text("Anna")')
    expect(page.locator("#categories-body tr")).to_have_count(2)


def row(page: Page, title: str) -> Any:
    return page.locator(f'#categories-body tr:has(td:text-is("{title}"))')


def test_add_a_category_below_games(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_categories(page, live_app_factory())
    page.click("#category-add")
    page.fill("#category-name", "Chess")
    page.select_option("#category-parent", label="Games")
    page.click("#category-save")
    expect(page.locator("#categories-body tr")).to_have_count(3)
    new = next(c for c in family(fake_server).categories.values() if c.title == "Chess")
    assert new.parent_id == "cgames"
    expect(row(page, "Chess").locator("td").first).to_have_attribute("data-depth", "1")


def test_an_empty_name_is_refused_in_the_dialog(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_categories(page, live_app_factory())
    pushes = fake_server.world.push_requests
    page.click("#category-add")
    page.click("#category-save")
    expect(page.locator('[data-error-for="title"]')).to_be_visible()
    assert fake_server.world.push_requests == pushes


def test_rename_a_category(page: Page, live_app_factory: Any, fake_server: Any) -> None:
    open_categories(page, live_app_factory())
    page.get_by_role("button", name="Edit Social").click()
    page.fill("#category-name", "Chat")
    page.click("#category-save")
    expect(row(page, "Chat")).to_be_visible()
    assert family(fake_server).categories["csocia"].title == "Chat"


def test_the_parent_choices_leave_out_the_category_and_its_sub_categories(
    page: Page, live_app_factory: Any
) -> None:
    open_categories(page, live_app_factory())
    page.get_by_role("button", name="Edit Games").click()
    options = page.locator("#category-parent option").all_text_contents()
    assert options == ["(top level)"]  # Games itself and Social below it are left out


def test_move_up_and_down_with_the_buttons(page: Page, live_app_factory: Any) -> None:
    open_categories(page, live_app_factory())
    page.click("#category-add")
    page.fill("#category-name", "Music")
    page.click("#category-save")
    expect(page.locator("#categories-body tr")).to_have_count(3)
    expect(page.get_by_role("button", name="Move down Music")).to_be_disabled()
    page.get_by_role("button", name="Move up Music").click()
    expect(page.locator("#categories-body tr").first).to_contain_text("Music")
    expect(page.get_by_role("button", name="Move up Music")).to_be_disabled()


def test_delete_asks_first_and_a_category_with_sub_categories_is_refused(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_categories(page, live_app_factory())
    page.get_by_role("button", name="Delete Games").click()
    expect(page.locator("#categories-error")).to_contain_text("sub-categories")
    assert "cgames" in family(fake_server).categories
    page.get_by_role("button", name="Delete Social").click()
    dialog = page.locator("#confirm-dialog")
    expect(dialog).to_contain_text("Delete the category Social")
    dialog.get_by_role("button", name="Delete").click()
    expect(page.locator("#categories-body tr")).to_have_count(1)
    assert "csocia" not in family(fake_server).categories


def test_cancelling_the_delete_keeps_the_category(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_categories(page, live_app_factory())
    page.get_by_role("button", name="Delete Social").click()
    page.locator("#confirm-dialog").get_by_role("button", name="Cancel").click()
    expect(page.locator("#categories-body tr")).to_have_count(2)
    assert "csocia" in family(fake_server).categories


def test_the_category_for_unassigned_apps_can_be_chosen(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_categories(page, live_app_factory())
    page.select_option("#category-unassigned", label="Social")
    expect(page.locator("#action-status")).to_contain_text("Done.")
    anna = next(u for u in family(fake_server).users.values() if u.name == "Anna")
    assert anna.category_for_unassigned == "csocia"
    page.reload()
    expect(page.locator("#category-unassigned")).to_have_value("csocia")


def test_limits_off_for_a_while_and_on_again(
    page: Page, live_app_factory: Any, fake_server: Any
) -> None:
    open_categories(page, live_app_factory())
    page.get_by_role("button", name="Limits off Games").click()
    page.fill("#limits-minutes", "45")
    page.locator("#limits-form button[type=submit]").click()
    expect(page.get_by_role("button", name="Limits on Games")).to_be_visible()
    assert family(fake_server).categories["cgames"].disable_limits_until > 0
    page.get_by_role("button", name="Limits on Games").click()
    expect(page.get_by_role("button", name="Limits off Games")).to_be_visible()
    assert family(fake_server).categories["cgames"].disable_limits_until == 0


def test_no_horizontal_scroll_at_phone_width(
    browser: Any, live_app_factory: Any
) -> None:
    live = live_app_factory()
    page = browser.new_context(
        locale="en-US", viewport={"width": 390, "height": 800}
    ).new_page()
    page.set_default_timeout(8000)
    open_categories(page, live)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
