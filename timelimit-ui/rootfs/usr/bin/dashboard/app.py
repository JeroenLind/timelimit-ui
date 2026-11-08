"""Entry point: ``py -3 app.py`` inside this folder (or ``py -3 -m dashboard`` one level up)."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
sys.path.insert(0, str(HERE.parent))

from dashboard.main import main

if __name__ == "__main__":
    raise SystemExit(main())
