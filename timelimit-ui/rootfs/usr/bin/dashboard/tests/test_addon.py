"""Plan step F2: add-on options become dashboard settings; config.yaml is a valid add-on definition."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from .. import addon
from ..config import load_settings

REPO = Path(__file__).resolve().parents[5]


def simple_yaml(path: Path) -> dict[str, Any]:
    """The tiny subset of YAML config.yaml uses (no extra dependency for one file)."""
    result: dict[str, Any] = {}
    section: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw.startswith(" ")
        line = raw.strip()
        if line.startswith("- "):
            assert section is not None
            result.setdefault(section, []).append(line[2:].strip().strip('"'))
        elif indented:
            assert section is not None
            key, _, value = line.partition(":")
            result.setdefault(section, {})[key.strip()] = parse_scalar(value)
        else:
            key, _, value = line.partition(":")
            if value.strip():
                result[key] = parse_scalar(value)
                section = None
            else:
                section = key
    return result


def parse_scalar(value: str) -> Any:
    text = value.strip().strip('"')
    if text in {"true", "false"}:
        return text == "true"
    return int(text) if re.fullmatch(r"\d+", text) else text


@pytest.fixture
def config() -> dict[str, Any]:
    return simple_yaml(REPO / "config.yaml")


# -- options -> settings ---------------------------------------------------------------------------


def test_defaults_when_there_is_no_options_file(tmp_path: Path) -> None:
    assert addon.read_options(tmp_path / "missing.json") == {}
    env = addon.environment_from_options({})
    assert env == {
        "DASHBOARD_HOST": "0.0.0.0",
        "DASHBOARD_PORT": "8099",
        "DASHBOARD_DATA_DIR": "/data",
        "DASHBOARD_LOG_LEVEL": "info",
    }


@pytest.mark.parametrize("level", ["debug", "info", "warning", "error"])
def test_a_sample_options_file_gives_valid_settings(tmp_path: Path, level: str) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"log_level": level}))
    env = addon.environment_from_options(addon.read_options(path))
    settings = load_settings({**env, "DASHBOARD_DATA_DIR": str(tmp_path)})
    assert settings.host == "0.0.0.0"
    assert settings.port == 8099
    assert settings.log_level == level.upper()


@pytest.mark.parametrize(
    "options",
    [{"log_level": "loud"}, {"server_url": "http://x"}, {"log_level": 3}],
)
def test_bad_options_are_refused_with_a_message(options: dict[str, Any]) -> None:
    with pytest.raises(addon.OptionsError):
        addon.environment_from_options(options)


def test_a_broken_options_file_is_refused(tmp_path: Path) -> None:
    for content in ("{", "[1]"):
        path = tmp_path / "options.json"
        path.write_text(content)
        with pytest.raises(addon.OptionsError):
            addon.read_options(path)


def test_main_reports_bad_options_and_does_not_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"log_level": "loud"}))
    assert addon.main(path) == 2
    assert "Invalid add-on options" in capsys.readouterr().err


# -- config.yaml -----------------------------------------------------------------------------------


def test_the_addon_is_aarch64_with_ingress(config: dict[str, Any]) -> None:
    assert config["arch"] == ["aarch64"]
    assert config["ingress"] is True
    assert config["ingress_port"] == addon.INGRESS_PORT
    assert "{arch}" in config["image"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", config["version"])
    for key in ("name", "description", "slug"):
        assert config[key]


def test_every_option_has_a_schema_entry_and_a_valid_default(
    config: dict[str, Any],
) -> None:
    assert set(config["options"]) == set(config["schema"]) == {"log_level"}
    allowed = re.fullmatch(r"list\((.+)\)", config["schema"]["log_level"])
    assert allowed is not None
    assert allowed.group(1).split("|") == list(addon.LOG_LEVELS)
    # the default option set maps to valid settings
    addon.environment_from_options(config["options"])


def test_the_server_is_not_an_add_on_option(config: dict[str, Any]) -> None:
    # design 8.1: the TimeLimit server is chosen in the settings screen
    assert "server_url" not in config["options"]
    assert "http" not in (REPO / "config.yaml").read_text()


def test_build_yaml_names_a_base_image_for_every_arch(config: dict[str, Any]) -> None:
    build = simple_yaml(REPO / "build.yaml")
    assert set(build["build_from"]) == set(config["arch"])
    assert all("aarch64" in image for image in build["build_from"].values())
