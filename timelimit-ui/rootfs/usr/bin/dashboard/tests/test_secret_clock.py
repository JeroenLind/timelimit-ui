"""Plan step A3: ``Secret`` hides itself, ``Clock`` is time-zone aware (TR-512, TR-513)."""

from __future__ import annotations

import copy
import logging
import pickle
from datetime import datetime, timedelta, timezone

import pytest

from dashboard.domain.clock import FakeClock, NaiveTimeError, require_aware
from dashboard.domain.secret import MASK, Secret, is_sensitive_field, mask
from dashboard.services.clock import SystemClock

VALUE = "tok-3f9a-very-secret"


def test_secret_is_masked_everywhere() -> None:
    secret = Secret(VALUE)
    assert repr(secret) == "Secret(***)"
    assert str(secret) == MASK
    assert f"{secret}" == MASK
    assert f"{secret:>6}" == "   ***"
    assert "%s" % secret == MASK  # noqa: UP031
    assert f"{secret}" == MASK
    assert VALUE not in repr([secret]) + repr({"k": secret})


def test_secret_is_masked_in_a_log_record(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        logging.getLogger("t").info("token is %s and %r", Secret(VALUE), Secret(VALUE))
    assert VALUE not in caplog.text
    assert "***" in caplog.text


def test_reveal_is_the_only_way_to_the_value() -> None:
    assert Secret(VALUE).reveal() == VALUE
    assert Secret(Secret(VALUE)).reveal() == VALUE


def test_secret_compares_and_has_a_truth_value() -> None:
    assert Secret("a") == Secret("a")
    assert Secret("a") != Secret("b")
    assert Secret("a") != "a"
    assert bool(Secret("a")) and not Secret("")


def test_secret_wraps_only_strings() -> None:
    with pytest.raises(TypeError):
        Secret(123)  # type: ignore[arg-type]


def test_secret_cannot_be_pickled_or_copied() -> None:
    with pytest.raises(TypeError):
        pickle.dumps(Secret(VALUE))
    with pytest.raises(TypeError):
        copy.deepcopy(Secret(VALUE))


def test_mask_and_sensitive_field_names() -> None:
    assert mask("anything") == MASK
    for name in [
        "token",
        "Auth_Token",
        "parent-password",
        "parentPasswordSecondHash",
        "SECRET_KEY",
    ]:
        assert is_sensitive_field(name), name
    for name in ["userId", "categoryId", "event", "status"]:
        assert not is_sensitive_field(name), name


def test_naive_time_is_refused() -> None:
    with pytest.raises(NaiveTimeError):
        require_aware(datetime(2026, 1, 1, 12, 0))
    with pytest.raises(NaiveTimeError):
        FakeClock(datetime(2026, 1, 1, 12, 0))
    with pytest.raises(NaiveTimeError):
        FakeClock().set(datetime(2026, 1, 1, 12, 0))


def test_fake_clock_is_aware_and_moves_only_when_told() -> None:
    clock = FakeClock()
    first = clock.now()
    assert first.tzinfo is not None
    assert clock.now() == first
    clock.advance(timedelta(hours=13))
    assert clock.now() == first + timedelta(hours=13)
    clock.set(datetime(2026, 3, 1, 23, 59, tzinfo=timezone(timedelta(hours=1))))
    clock.advance(timedelta(minutes=1))
    assert (clock.now().month, clock.now().day, clock.now().hour) == (3, 2, 0)


def test_system_clock_is_aware_and_close_to_now() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert abs(now - datetime.now(timezone.utc)) < timedelta(seconds=5)
