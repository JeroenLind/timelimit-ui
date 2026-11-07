"""Environment for the kept old tests (class K in docs/plan/old-tests-disposition.md).

These tests exercise modules of the old ``dashboardV2`` package that the rebuild reuses
(action builder/pusher, key manager) and ``crypto_utils``. Until the modules move into
``dashboard/`` (plan B2/B4) they are imported from their old place. The old modules read their
paths from the environment at import time, so it is pointed at a throw-away folder first; nothing
is written inside the repository.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

BIN = Path(__file__).resolve().parents[3]  # rootfs/usr/bin
LEGACY = BIN / "dashboardV2"

_scratch = Path(tempfile.mkdtemp(prefix="dashboard-kept-"))
atexit.register(shutil.rmtree, _scratch, ignore_errors=True)

os.environ["DATABASE_PATH"] = str(_scratch / "legacy.db")
os.environ["LOG_FILE_PATH"] = str(_scratch / "dashboardV2.log")
os.environ["LOG_WERKZEUG_FILE_PATH"] = str(_scratch / "werkzeug.log")
os.environ["LOG_ROTATE_ON_START"] = "false"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["SKIP_PORT_CHECK"] = "true"

for folder in (str(BIN), str(LEGACY)):
    if folder not in sys.path:
        sys.path.insert(0, folder)
