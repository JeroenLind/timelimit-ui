"""Fixtures of the new suite: every test gets its own temporary data folder (plan A2, TR-500).

Nothing in the repository tree is used or written by a test; everything lives under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """The data folder of one test (own database, secret key, logs, session files)."""
    folder = tmp_path / "data"
    folder.mkdir()
    return folder


@pytest.fixture
def db_path(data_dir: Path) -> Path:
    """Path of the test's own SQLite file. The file is not created; the code under test does that."""
    return data_dir / "dashboard.db"


@pytest.fixture
def log_dir(data_dir: Path) -> Path:
    """The test's own log folder."""
    folder = data_dir / "logs"
    folder.mkdir()
    return folder
