"""Plan step C2: no module that remains imports a removed legacy module (TR-312)."""

from __future__ import annotations

import importlib
import pkgutil

import dashboard

REMOVED = ("web_server", "api_client", "check_server", "frontend")


def test_every_remaining_module_imports() -> None:
    names = [
        m.name
        for m in pkgutil.walk_packages(dashboard.__path__, "dashboard.")
        if ".tests" not in m.name and not m.name.endswith("__main__")
    ]
    assert names
    for name in names:
        importlib.import_module(name)
    importlib.import_module("crypto_utils")


def test_no_source_file_imports_a_removed_module() -> None:
    import ast
    from pathlib import Path

    bin_dir = Path(dashboard.__file__).resolve().parent.parent
    for path in bin_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found = [node.module.split(".")[0]]
            else:
                continue
            assert not set(found) & set(REMOVED), f"{path}: {found}"
