"""Plan step A3: settings precedence, validation, defaults, secret key (TR-301, 305, 306, 400, 401)."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from dashboard.config import (
    CONFIG_FILE_NAME,
    DATA_DIR_ENV,
    PARSERS,
    SECRET_KEY_ENV,
    SECRET_KEY_FILE_NAME,
    ConfigError,
    Settings,
    ensure_data_dir,
    env_name,
    load_secret_key,
    load_settings,
    setting_names,
)

# setting -> (default, value in the file, value from the environment as text, expected env value)
TABLE: dict[str, tuple[Any, Any, str, Any]] = {
    "host": ("127.0.0.1", "0.0.0.0", "10.1.2.3", "10.1.2.3"),
    "port": (8100, 9001, "9002", 9002),
    "log_level": ("INFO", "debug", "error", "ERROR"),
    "log_max_bytes": (10 * 1024 * 1024, 2048, "4096", 4096),
    "log_backup_count": (5, 2, "3", 3),
    "health_timeout": (3.0, 1.5, "2.5", 2.5),
    "health_interval": (5.0, 2, "4", 4.0),
    "backoff_initial": (10.0, 5, "6", 6.0),
    "backoff_max": (30.0, 40, "50", 50.0),
    "sync_target": (5.0, 7, "8", 8.0),
    "poll_interval": (30.0, 15, "20", 20.0),
    "retry_delay": (0.25, 0.5, "0.75", 0.75),
    "retry_count": (2, 3, "4", 4),
    "browser_timeout": (10.0, 11, "12", 12.0),
    "server_timeout": (10.0, 13, "14", 14.0),
    "test_server": (False, True, "false", False),
    "server_url": (
        "",
        "https://a.example.org",
        "http://localhost:8080/",
        "http://localhost:8080",
    ),
}
FILE_EXPECTED = {
    "host": "0.0.0.0",
    "port": 9001,
    "log_level": "DEBUG",
    "log_max_bytes": 2048,
    "log_backup_count": 2,
    "health_timeout": 1.5,
    "health_interval": 2.0,
    "backoff_initial": 5.0,
    "backoff_max": 40.0,
    "sync_target": 7.0,
    "poll_interval": 15.0,
    "retry_delay": 0.5,
    "retry_count": 3,
    "browser_timeout": 11.0,
    "server_timeout": 13.0,
    "test_server": True,
    "server_url": "https://a.example.org",
}


def _write_file(data_dir: Path, content: Any) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / CONFIG_FILE_NAME).write_text(json.dumps(content), encoding="utf-8")


def test_the_table_covers_every_setting() -> None:
    assert set(TABLE) == set(PARSERS)
    assert set(TABLE) | {"data_dir"} == set(setting_names())


def test_defaults_are_the_agreed_values(tmp_path: Path) -> None:
    settings = load_settings({DATA_DIR_ENV: str(tmp_path)})
    for name, (default, *_rest) in TABLE.items():
        assert getattr(settings, name) == default, name
    assert settings.data_dir == tmp_path
    assert settings.log_file == tmp_path / "logs" / "dashboard.log"


def test_default_listen_address_and_port_are_localhost_8100() -> None:
    assert (Settings().host, Settings().port) == ("127.0.0.1", 8100)


def test_default_data_folder_is_next_to_the_app(tmp_path: Path) -> None:
    assert load_settings({}, app_dir=tmp_path).data_dir == tmp_path / "data"


@pytest.mark.parametrize("name", sorted(TABLE))
def test_file_beats_default(name: str, tmp_path: Path) -> None:
    _write_file(tmp_path, {name: TABLE[name][1]})
    settings = load_settings({DATA_DIR_ENV: str(tmp_path)})
    assert getattr(settings, name) == FILE_EXPECTED[name]


@pytest.mark.parametrize("name", sorted(TABLE))
def test_environment_beats_file_and_default(name: str, tmp_path: Path) -> None:
    _write_file(tmp_path, {name: TABLE[name][1]})
    env = {DATA_DIR_ENV: str(tmp_path), env_name(name): TABLE[name][2]}
    assert getattr(load_settings(env), name) == TABLE[name][3]


def test_file_and_environment_mix_per_setting(tmp_path: Path) -> None:
    _write_file(tmp_path, {"port": 9001, "host": "0.0.0.0"})
    settings = load_settings({DATA_DIR_ENV: str(tmp_path), "DASHBOARD_PORT": "9002"})
    assert (settings.host, settings.port) == ("0.0.0.0", 9002)


@pytest.mark.parametrize(
    ("name", "bad"),
    [
        ("port", "abc"),
        ("port", "-1"),
        ("port", "70000"),
        ("port", "80.5"),
        ("host", "  "),
        ("log_level", "loud"),
        ("log_max_bytes", "0"),
        ("log_backup_count", "0"),
        ("health_timeout", "0"),
        ("health_timeout", "-3"),
        ("health_timeout", "soon"),
        ("health_timeout", "nan"),
        ("sync_target", "inf"),
        ("test_server", "maybe"),
        ("server_url", "http://example.org"),
        ("health_interval", "0"),
    ],
)
def test_invalid_environment_value_names_the_setting(
    name: str, bad: str, tmp_path: Path
) -> None:
    with pytest.raises(ConfigError) as error:
        load_settings({DATA_DIR_ENV: str(tmp_path), env_name(name): bad})
    assert env_name(name) in str(error.value)
    assert repr(bad) in str(error.value)


def test_invalid_file_value_names_file_and_setting(tmp_path: Path) -> None:
    _write_file(tmp_path, {"port": "abc", "log_level": 7})
    with pytest.raises(ConfigError) as error:
        load_settings({DATA_DIR_ENV: str(tmp_path)})
    message = str(error.value)
    assert "config.json setting 'port'" in message
    assert "config.json setting 'log_level'" in message


def test_all_problems_are_reported_at_once(tmp_path: Path) -> None:
    env = {
        DATA_DIR_ENV: str(tmp_path),
        "DASHBOARD_PORT": "x",
        "DASHBOARD_HEALTH_TIMEOUT": "0",
    }
    with pytest.raises(ConfigError) as error:
        load_settings(env)
    assert "DASHBOARD_PORT" in str(error.value)
    assert "DASHBOARD_HEALTH_TIMEOUT" in str(error.value)


def test_unknown_setting_and_data_dir_in_the_file_are_refused(tmp_path: Path) -> None:
    _write_file(tmp_path, {"prot": 1, "data_dir": "/x"})
    with pytest.raises(ConfigError) as error:
        load_settings({DATA_DIR_ENV: str(tmp_path)})
    assert "unknown setting 'prot'" in str(error.value)
    assert DATA_DIR_ENV in str(error.value)


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_a_broken_config_file_is_a_clear_error(content: str, tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE_NAME).write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings({DATA_DIR_ENV: str(tmp_path)})


def test_backoff_max_must_not_be_below_initial(tmp_path: Path) -> None:
    env = {
        DATA_DIR_ENV: str(tmp_path),
        "DASHBOARD_BACKOFF_INITIAL": "20",
        "DASHBOARD_BACKOFF_MAX": "5",
    }
    with pytest.raises(ConfigError):
        load_settings(env)


def test_log_level_accepts_the_documented_spellings(tmp_path: Path) -> None:
    for text, expected in [
        ("DEBUG", "DEBUG"),
        ("warn", "WARNING"),
        ("Warning", "WARNING"),
    ]:
        settings = load_settings(
            {DATA_DIR_ENV: str(tmp_path), "DASHBOARD_LOG_LEVEL": text}
        )
        assert settings.log_level == expected


def test_ensure_data_dir_creates_data_and_log_folder(tmp_path: Path) -> None:
    settings = load_settings({DATA_DIR_ENV: str(tmp_path / "new" / "data")})
    ensure_data_dir(settings)
    assert settings.data_dir.is_dir() and settings.log_dir.is_dir()
    ensure_data_dir(settings)  # a second start is fine


# ---- secret key (TR-306)


def test_secret_key_is_created_once_and_kept(data_dir: Path) -> None:
    settings = load_settings({DATA_DIR_ENV: str(data_dir)})
    first = load_secret_key(settings, {})
    second = load_secret_key(settings, {})
    assert first == second
    assert len(first.reveal()) >= 32
    assert (data_dir / SECRET_KEY_FILE_NAME).read_text(
        encoding="utf-8"
    ).strip() == first.reveal()


def test_secret_key_differs_between_installations(tmp_path: Path) -> None:
    keys = set()
    for name in ["a", "b"]:
        folder = tmp_path / name
        settings = load_settings({DATA_DIR_ENV: str(folder)})
        keys.add(load_secret_key(settings, {}).reveal())
    assert len(keys) == 2


def test_environment_overrides_the_secret_key_and_writes_no_file(
    data_dir: Path,
) -> None:
    settings = load_settings({DATA_DIR_ENV: str(data_dir)})
    key = load_secret_key(settings, {SECRET_KEY_ENV: "from-the-environment"})
    assert key.reveal() == "from-the-environment"
    assert not (data_dir / SECRET_KEY_FILE_NAME).exists()


def test_an_interrupted_first_start_does_not_leave_a_bad_key(data_dir: Path) -> None:
    (data_dir / SECRET_KEY_FILE_NAME).write_text("", encoding="utf-8")
    settings = load_settings({DATA_DIR_ENV: str(data_dir)})
    key = load_secret_key(settings, {})
    assert len(key.reveal()) >= 32
    assert load_secret_key(settings, {}) == key
    assert not list(data_dir.glob("*.tmp"))


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permission bits")
def test_secret_key_file_is_private(data_dir: Path) -> None:
    load_secret_key(load_settings({DATA_DIR_ENV: str(data_dir)}), {})
    mode = stat.S_IMODE(os.stat(data_dir / SECRET_KEY_FILE_NAME).st_mode)
    assert mode & 0o077 == 0


def test_the_key_is_never_visible_in_text(data_dir: Path) -> None:
    key = load_secret_key(load_settings({DATA_DIR_ENV: str(data_dir)}), {})
    assert key.reveal() not in f"{key} {key!r}"
