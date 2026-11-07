"""Plan step A1: the new package imports and has one folder per layer (decision Q2)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1]
CODE_LAYERS = ["routes", "services", "repository", "domain", "sync", "client"]
ASSET_FOLDERS = ["static", "templates"]


def test_package_imports() -> None:
    assert importlib.import_module("dashboard").__doc__


@pytest.mark.parametrize("layer", CODE_LAYERS)
def test_layer_is_an_importable_package(layer: str) -> None:
    module = importlib.import_module(f"dashboard.{layer}")
    assert Path(module.__file__ or "").parent == PACKAGE_DIR / layer


@pytest.mark.parametrize("folder", ASSET_FOLDERS)
def test_asset_folder_exists(folder: str) -> None:
    assert (PACKAGE_DIR / folder).is_dir()
