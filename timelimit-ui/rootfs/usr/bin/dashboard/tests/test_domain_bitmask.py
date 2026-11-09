"""Blocked-times strings and day masks (B2, TR-100)."""

from __future__ import annotations

import random

import pytest

from dashboard.domain import bitmask as bm
from dashboard.domain.bitmask import BitmaskError


def test_empty_means_nothing_blocked() -> None:
    assert bm.format_blocked_times([]) == ""
    assert bm.parse_blocked_times("") == []


def test_known_values() -> None:
    # Monday 08:00-12:00 and Sunday 22:00-24:00
    intervals = [(480, 720), (6 * 1440 + 1320, 7 * 1440)]
    text = bm.format_blocked_times(intervals)
    assert text == "480,720,9960,10080"
    assert bm.parse_blocked_times(text) == intervals


@pytest.mark.parametrize(
    "intervals",
    [
        [(5, 5)],  # empty interval
        [(10, 5)],  # reversed
        [(0, 10), (10, 20)],  # touching: the server wants strictly increasing numbers
        [(0, 10), (5, 20)],  # overlapping
        [(20, 30), (0, 10)],  # unsorted
        [(-1, 10)],
        [(0, 10081)],
    ],
)
def test_invalid_intervals_are_rejected(intervals: list[tuple[int, int]]) -> None:
    with pytest.raises(BitmaskError):
        bm.format_blocked_times(intervals)


@pytest.mark.parametrize(
    "text", ["1", "1,2,3", "a,b", "1,,2", "5,3", "0,10081", "-1,5", "1,2,2,3", " 1,2"]
)
def test_invalid_strings_are_rejected(text: str) -> None:
    with pytest.raises(BitmaskError):
        bm.parse_blocked_times(text)


def test_round_trip_property() -> None:
    rng = random.Random(20261109)
    for _ in range(500):
        points = sorted(
            rng.sample(range(bm.MINUTES_PER_WEEK + 1), rng.choice([0, 2, 4, 10, 40]))
        )
        intervals = list(zip(points[0::2], points[1::2], strict=True))
        assert bm.parse_blocked_times(bm.format_blocked_times(intervals)) == intervals


def test_merge_makes_any_input_valid_property() -> None:
    rng = random.Random(7)
    for _ in range(300):
        raw = []
        for _ in range(rng.randint(0, 12)):
            start = rng.randint(0, bm.MINUTES_PER_WEEK - 1)
            raw.append((start, rng.randint(start + 1, bm.MINUTES_PER_WEEK)))
        merged = bm.merge_intervals(raw)
        bm.validate_intervals(merged)  # must not raise
        covered = {m for s, e in raw for m in range(s, e)}
        assert {m for s, e in merged for m in range(s, e)} == covered


def test_day_mask_bit_zero_is_monday() -> None:
    assert bm.day_mask([0]) == 1
    assert bm.day_mask([6]) == 64
    assert bm.day_mask(range(7)) == bm.ALL_DAYS_MASK
    assert bm.days_from_mask(0b0100101) == [0, 2, 5]


def test_day_mask_round_trip_all_masks() -> None:
    for mask in range(128):
        assert bm.day_mask(bm.days_from_mask(mask)) == mask


def test_remove_and_restore_today_bit() -> None:
    """FR-307: remove today's bit and put it back later; the other days stay."""
    for weekday in range(7):
        for mask in range(128):
            off = bm.mask_without_day(mask, weekday)
            assert not bm.mask_has_day(off, weekday)
            assert off | (mask & (1 << weekday)) == mask
            if bm.mask_has_day(mask, weekday):
                assert bm.mask_with_day(off, weekday) == mask


@pytest.mark.parametrize("value", [-1, 7, True, "1"])
def test_bad_weekday_is_rejected(value: object) -> None:
    with pytest.raises(BitmaskError):
        bm.day_mask([value])  # type: ignore[list-item]


def test_week_minute() -> None:
    assert bm.week_minute(0, 0) == 0
    assert bm.week_minute(6, 1440) == bm.MINUTES_PER_WEEK
    with pytest.raises(BitmaskError):
        bm.week_minute(0, 1441)


def test_day_of_epoch_uses_the_childs_date() -> None:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    late = datetime(
        2026, 11, 8, 23, 30, tzinfo=timezone.utc
    )  # already 9 Nov in Amsterdam
    assert bm.day_of_epoch(late, timezone.utc) == 20765
    assert bm.day_of_epoch(late, ZoneInfo("Europe/Amsterdam")) == 20766
    with pytest.raises(BitmaskError):
        bm.day_of_epoch(datetime(2026, 11, 8), timezone.utc)
