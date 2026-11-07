"""Plan step A1: the baseline comparison logic (the suite itself is run by hand)."""

from __future__ import annotations

import baseline

SAMPLE = """
FAILED tests/test_a.py::TestA::test_one - assert 1 == 2
FAILED tests/test_b.py::test_two
4 failed, 1321 passed, 1 warning in 198.0s (0:03:17)
"""


def test_parsers() -> None:
    assert baseline.parse_failed(SAMPLE) == [
        "tests/test_a.py::TestA::test_one",
        "tests/test_b.py::test_two",
    ]
    assert baseline.parse_passed(SAMPLE) == 1321
    assert baseline.parse_collected("1325 tests collected in 0.25s") == 1325


def _record(known: list[str]) -> dict:
    return {
        "collected": 1325,
        "platforms": {baseline.platform_key(): {"failed": known}},
    }


def test_same_result_is_ok() -> None:
    assert baseline.compare(_record(["x"]), 1325, ["x"]) == []


def test_fewer_failures_is_ok() -> None:
    assert baseline.compare(_record(["x", "y"]), 1325, ["x"]) == []


def test_new_failure_or_count_change_is_reported() -> None:
    assert baseline.compare(_record(["x"]), 1325, ["x", "z"]) != []
    assert baseline.compare(_record(["x"]), 1300, ["x"]) != []


def test_platform_without_record_only_compares_the_count() -> None:
    record = {"collected": 1325, "platforms": {}}
    assert baseline.compare(record, 1325, ["anything"]) == []
