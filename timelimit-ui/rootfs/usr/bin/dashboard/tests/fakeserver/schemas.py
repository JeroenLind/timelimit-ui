"""Strict request schemas of the TimeLimit server and the response schema built from them (plan A5).

The schemas are extracted from the server's own ``validator.ts`` by ``tools/extract_server_schemas.py``,
so the fake rejects exactly what the real server rejects (``additionalProperties: false``).
"""

from __future__ import annotations

import json
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_FILE = Path(__file__).with_name("server_schemas.json")


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_FILE.read_text(encoding="utf-8"))
    return data


def definitions() -> dict[str, Any]:
    found: dict[str, Any] = _data()["definitions"]
    return found


@cache
def request_validator(name: str) -> Draft7Validator:
    """Validator for ``isXxx`` of the server, with the shared definitions attached."""
    schema = dict(_data()["validators"][name])
    schema["definitions"] = definitions()
    return Draft7Validator(schema)


def is_valid(name: str, body: Any) -> bool:
    return bool(request_validator(name).is_valid(body))


def errors(name: str, body: Any) -> list[str]:
    return [e.message for e in request_validator(name).iter_errors(body)]


def _ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/definitions/{name}"}


def _list_of(name: str) -> dict[str, Any]:
    return {"type": "array", "items": _ref(name)}


# ServerDataStatus lives in server/object/serverdatastatus.ts; its parts are in the definitions.
SERVER_DATA_STATUS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fullVersion", "apiLevel"],
    "properties": {
        "devices": _ref("ServerDeviceList"),
        "devices2": _list_of("ServerExtendedDeviceData"),
        "apps": _list_of("ServerInstalledAppsData"),
        "rmCategories": {"type": "array", "items": {"type": "string"}},
        "categoryBase": _list_of("ServerUpdatedCategoryBaseData"),
        "categoryApp": _list_of("ServerUpdatedCategoryAssignedApps"),
        "usedTimes": _list_of("ServerUpdatedCategoryUsedTimes"),
        "rules": _list_of("ServerUpdatedTimeLimitRules"),
        "tasks": _list_of("ServerUpdatedCategoryTasks"),
        "users": _ref("ServerUserList"),
        "krq": _list_of("ServerKeyRequest"),
        "kr": _list_of("ServerKeyResponse"),
        "pings": _list_of("ServerPing"),
        "dh": _ref("ServerDhKey"),
        "u2f": _ref("U2fData"),
        "fullVersion": {"type": "number"},
        "message": {"type": "string"},
        "apiLevel": {"type": "number"},
    },
}


@lru_cache(maxsize=1)
def _status_validator() -> Draft7Validator:
    schema = dict(SERVER_DATA_STATUS)
    schema["definitions"] = definitions()
    return Draft7Validator(schema)


def status_errors(body: Any) -> list[str]:
    """Why a (fake) server answer would break a strict client; empty list when it is fine."""
    return [
        f"{'/'.join(map(str, e.absolute_path))}: {e.message}"
        for e in _status_validator().iter_errors(body)
    ]
