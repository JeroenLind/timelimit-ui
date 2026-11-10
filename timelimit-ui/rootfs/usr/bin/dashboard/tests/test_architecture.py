"""Plan step B7: the layer rules and three code standards, checked on the import graph (TR-308, TR-512, 513, 514).

This is static analysis of the syntax tree, not a search for names in text: imports are resolved (also
relative ones and imports inside functions), calls are found by their shape. ``analyse`` takes the
package folder so the self-tests at the bottom can prove that every rule really fails on a violation.

Layer table (design section 2.1; "foundation" = ``config`` and ``logs``):

==========  ===============================================================
domain      domain
client      domain, client
repository  domain, repository, foundation
sync        domain, client, repository, sync, foundation
services    domain, repository, sync, services, foundation
routes      domain, services, routes, foundation, ``sync.hub`` (the SSE hub)
foundation  domain, foundation, ``client`` (``config`` validates the server URL with it)
top         everything: ``factory``, ``main``, ``app``, ``__main__`` wire the parts together
==========  ===============================================================
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGE = "dashboard"
PACKAGE_DIR = Path(__file__).resolve().parents[1]

ALLOWED: dict[str, set[str]] = {
    "domain": {"domain"},
    "client": {"domain", "client"},
    "repository": {"domain", "repository", "foundation"},
    "sync": {"domain", "client", "repository", "sync", "foundation"},
    "services": {"domain", "repository", "sync", "services", "foundation"},
    "routes": {"domain", "services", "routes", "foundation", "sync.hub"},
    "foundation": {"domain", "foundation", "client"},
}
FOUNDATION = {"config", "logs"}
TOP = {"factory", "main", "app", "__main__", "__init__"}

# Written exceptions to the table, each with its reason. Keep this list short.
EXCEPTIONS: dict[tuple[str, str], str] = {
    (
        "services.connection",
        "client",
    ): "the health check of the server (design 2.1: timers may call the client, health only)",
}

# Third-party and standard library modules that only certain parts may import.
RESTRICTED_IMPORTS: dict[str, tuple[str, ...]] = {
    "sqlite3": ("repository",),
    "requests": ("client",),
    "urllib3": ("client",),
    "urllib.request": ("client",),
    "http.client": ("client",),
    "socketio": ("sync.live",),
    "engineio": ("sync.live",),
    "flask": ("routes", "factory", "main", "app"),
    "werkzeug": ("routes", "factory", "main", "app"),
}
# Nothing here may be imported by the domain: it has no I/O at all.
DOMAIN_FORBIDDEN = {
    "sqlite3", "socket", "socketio", "engineio", "requests", "urllib3", "http", "flask", "werkzeug",
    "subprocess", "threading", "asyncio", "logging", "shutil", "pathlib", "tempfile", "dashboard.logs",
}  # fmt: skip
CLOCK_MODULE = "domain.clock"  # the one place that may read the real clock (TR-512)

HTTP_VERBS = {"get", "post", "put", "delete", "patch", "head", "request", "send"}
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}
LOG_RECEIVERS = {"log", "logger", "_log", "_logger", "logging"}
SECRET_NAME = re.compile(r"token|secret|password|passwd|hash|reveal", re.IGNORECASE)


def modules(package_dir: Path, package: str = PACKAGE) -> Iterator[tuple[str, Path]]:
    """(module name relative to the package, file) for every source file; tests and caches excluded."""
    for path in sorted(package_dir.rglob("*.py")):
        relative = path.relative_to(package_dir)
        if "tests" in relative.parts or "__pycache__" in relative.parts:
            continue
        name = ".".join(relative.with_suffix("").parts)
        yield (name.removesuffix(".__init__")), path


def part_of(module: str) -> str:
    head = module.split(".")[0]
    if head in FOUNDATION:
        return "foundation"
    if head in TOP:
        return "top"
    return head


def imports_of(module: str, path: Path, package: str) -> Iterator[tuple[str, int]]:
    """Every imported module name, absolute, with its line. Relative imports are resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    is_package = path.name == "__init__.py"
    base = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = (
                    base[: len(base) - (node.level - 1)] if node.level > 1 else base
                )
                target = ".".join(
                    [package, *anchor, *([node.module] if node.module else [])]
                )
            else:
                target = node.module or ""
            yield target, node.lineno
            for alias in node.names:  # `from . import x` imports the module x
                yield f"{target}.{alias.name}", node.lineno


def internal(name: str, package: str) -> str | None:
    """``dashboard.sync.hub`` -> ``sync.hub``; None for anything outside the package."""
    if name == package:
        return ""
    return name[len(package) + 1 :] if name.startswith(package + ".") else None


def is_under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def check_layers(package_dir: Path, package: str) -> list[str]:
    problems: list[str] = []
    for module, path in modules(package_dir, package):
        part = part_of(module)
        for target, line in imports_of(module, path, package):
            inner = internal(target, package)
            if inner is None or inner == "":
                continue
            target_part = part_of(inner)
            if part == "top" or target_part == part or target_part == "top":
                continue
            allowed = ALLOWED.get(part, set())
            if any(a.startswith(inner + ".") for a in allowed):
                continue  # `from pkg.sync import hub` names the package sync; the module sync.hub is checked
            ok = target_part in allowed or any(
                is_under(inner, a) for a in allowed if "." in a
            )
            if not ok and (module, target_part) not in EXCEPTIONS:
                problems.append(
                    f"{module}:{line} imports {inner}, but {part} may only use {sorted(allowed)}"
                )
    return problems


def check_restricted_imports(package_dir: Path, package: str) -> list[str]:
    problems: list[str] = []
    for module, path in modules(package_dir, package):
        for target, line in imports_of(module, path, package):
            for restricted, owners in RESTRICTED_IMPORTS.items():
                if is_under(target, restricted) and not any(
                    is_under(module, owner) for owner in owners
                ):
                    problems.append(
                        f"{module}:{line} imports {target}; only {list(owners)} may"
                    )
            if part_of(module) == "domain" and any(
                is_under(target, bad) for bad in DOMAIN_FORBIDDEN
            ):
                problems.append(
                    f"{module}:{line} imports {target}; the domain has no I/O"
                )
    return problems


def check_domain_clock(package_dir: Path, package: str) -> list[str]:
    """TR-512: the domain never reads the clock itself; it is handed the time."""
    problems: list[str] = []
    for module, path in modules(package_dir, package):
        if part_of(module) != "domain" or module == CLOCK_MODULE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            owner = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
            name = node.func.attr
            if name in {"now", "utcnow", "today"} or (
                owner == "time" and name in {"time", "monotonic", "sleep"}
            ):
                problems.append(
                    f"{module}:{node.lineno} reads the clock with {owner}.{name}(); inject a Clock"
                )
    return problems


def check_secrets_in_logs(package_dir: Path, package: str) -> list[str]:
    """TR-513: nothing that looks like a secret is formatted into a log call; use ``Secret`` (masked)."""
    problems: list[str] = []
    for module, path in modules(package_dir, package):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in LOG_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in LOG_RECEIVERS
            ):
                continue
            for part in [*node.args, *(kw.value for kw in node.keywords)]:
                for inner in ast.walk(part):
                    text = (
                        inner.id
                        if isinstance(inner, ast.Name)
                        else inner.attr
                        if isinstance(inner, ast.Attribute)
                        else ""
                    )
                    if text and SECRET_NAME.search(text):
                        problems.append(
                            f"{module}:{node.lineno} puts `{text}` into a log call"
                        )
    return problems


def check_timeouts(package_dir: Path, package: str) -> list[str]:
    """TR-514: every HTTP call has an explicit ``timeout=``."""
    problems: list[str] = []
    for module, path in modules(package_dir, package):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        uses_http = any(
            target.split(".")[0] in {"requests", "urllib3"}
            or target.startswith("urllib.request")
            for target, _ in imports_of(module, path, package)
        )
        if not uses_http:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else ""
            )
            owner = (
                ast.unparse(func.value).lower()
                if isinstance(func, ast.Attribute)
                else ""
            )
            is_http = name == "urlopen" or (
                name in HTTP_VERBS
                and any(word in owner for word in ("requests", "session", "http"))
            )
            if is_http and not any(kw.arg == "timeout" for kw in node.keywords):
                problems.append(
                    f"{module}:{node.lineno} calls {ast.unparse(func)}() without timeout="
                )
    return problems


CHECKS = {
    "layers": check_layers,
    "restricted imports": check_restricted_imports,
    "domain clock": check_domain_clock,
    "secrets in logs": check_secrets_in_logs,
    "timeouts": check_timeouts,
}


def analyse(package_dir: Path, package: str = PACKAGE) -> dict[str, list[str]]:
    return {name: check(package_dir, package) for name, check in CHECKS.items()}


# -- the real package ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("rule", list(CHECKS))
def test_the_dashboard_package_follows_the_rule(rule: str) -> None:
    problems = CHECKS[rule](PACKAGE_DIR, PACKAGE)
    assert problems == [], "\n".join(problems)


def test_every_exception_is_still_needed() -> None:
    """A written exception that no longer matches an import is clutter: remove it."""
    used: set[tuple[str, str]] = set()
    for module, path in modules(PACKAGE_DIR, PACKAGE):
        for target, _ in imports_of(module, path, PACKAGE):
            inner = internal(target, PACKAGE)
            if inner:
                used.add((module, part_of(inner)))
    assert set(EXCEPTIONS) <= used


def test_the_layer_check_sees_something() -> None:
    """Guard against a check that passes because it scans nothing."""
    names = [m for m, _ in modules(PACKAGE_DIR, PACKAGE)]
    assert (
        "routes.server" in names
        and "domain.actions" in names
        and "repository.cache" in names
    )
    edges = sum(
        1
        for module, path in modules(PACKAGE_DIR, PACKAGE)
        for target, _ in imports_of(module, path, PACKAGE)
        if internal(target, PACKAGE)
    )
    assert edges > 30


# -- self-tests: each rule fails on a scratch violation -----------------------------------------------------------------------------


def scratch(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "pkg"
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def run(tmp_path: Path, files: dict[str, str]) -> dict[str, list[str]]:
    return analyse(scratch(tmp_path, files), package="pkg")


def test_a_route_importing_the_repository_fails(tmp_path: Path) -> None:
    found = run(
        tmp_path,
        {
            "routes/x.py": "from pkg.repository import cache\n",
            "repository/cache.py": "",
        },
    )
    assert (
        found["layers"]
        and "routes/x" not in found["layers"][0]
        and "routes.x" in found["layers"][0]
    )


def test_relative_imports_are_resolved(tmp_path: Path) -> None:
    found = run(
        tmp_path,
        {"routes/x.py": "from ..client import server\n", "client/server.py": ""},
    )
    assert any("routes.x" in p for p in found["layers"])


def test_an_import_inside_a_function_is_found(tmp_path: Path) -> None:
    found = run(
        tmp_path,
        {
            "services/s.py": "def f():\n    from pkg.client import server\n",
            "client/server.py": "",
        },
    )
    assert any("services.s" in p for p in found["layers"])


def test_the_sse_hub_is_the_one_sync_module_routes_may_use(tmp_path: Path) -> None:
    files = {
        "routes/a.py": "from pkg.sync import hub\n",
        "sync/hub.py": "",
        "sync/pull.py": "",
    }
    assert run(tmp_path, files)["layers"] == []
    files["routes/b.py"] = "from pkg.sync import pull\n"
    assert any("routes.b" in p for p in run(tmp_path / "again", files)["layers"])


def test_the_domain_importing_another_layer_fails(tmp_path: Path) -> None:
    found = run(
        tmp_path,
        {"domain/a.py": "from pkg.repository import db\n", "repository/db.py": ""},
    )
    assert any("domain.a" in p for p in found["layers"])


def test_sqlite3_outside_the_repository_fails(tmp_path: Path) -> None:
    found = run(
        tmp_path,
        {"services/a.py": "import sqlite3\n", "repository/db.py": "import sqlite3\n"},
    )
    assert (
        len(found["restricted imports"]) == 1
        and "services.a" in found["restricted imports"][0]
    )


def test_the_http_library_outside_the_client_fails(tmp_path: Path) -> None:
    found = run(
        tmp_path, {"sync/a.py": "import requests\n", "client/c.py": "import requests\n"}
    )
    assert (
        len(found["restricted imports"]) == 1
        and "sync.a" in found["restricted imports"][0]
    )


def test_io_in_the_domain_fails(tmp_path: Path) -> None:
    found = run(tmp_path, {"domain/a.py": "import socket\nimport logging\n"})
    assert len(found["restricted imports"]) == 2


def test_the_domain_reading_the_clock_fails_except_in_the_clock_module(
    tmp_path: Path,
) -> None:
    files = {
        "domain/a.py": "import datetime, time\nx = datetime.datetime.now()\ny = time.time()\n",
        "domain/clock.py": "import datetime\nx = datetime.datetime.now()\n",
    }
    found = run(tmp_path, files)["domain clock"]
    assert len(found) == 2 and all("domain.a" in p for p in found)


def test_a_secret_in_a_log_call_fails_and_a_safe_one_passes(tmp_path: Path) -> None:
    files = {
        "sync/bad.py": "log.info(f'token is {device_token}')\nlog.debug('x', extra={'p': self.password})\n",
        "sync/good.py": "log.info('pulled', extra={'count': n})\nlog.info('url %s', url)\n",
    }
    found = run(tmp_path, files)["secrets in logs"]
    assert len(found) == 2 and all("sync.bad" in p for p in found)


def test_an_http_call_without_timeout_fails(tmp_path: Path) -> None:
    files = {
        "client/bad.py": "import requests\nrequests.get('u')\nself._session.request('GET', 'u')\n",
        "client/good.py": "import requests\nrequests.get('u', timeout=3)\nself._session.request('GET', 'u', timeout=3)\n",
    }
    found = run(tmp_path, files)["timeouts"]
    assert len(found) == 2 and all("client.bad" in p for p in found)


def test_a_clean_scratch_package_passes_every_rule(tmp_path: Path) -> None:
    files = {
        "domain/a.py": "x = 1\n",
        "repository/db.py": "import sqlite3\nfrom pkg.domain import a\n",
        "services/s.py": "from pkg.repository import db\n",
        "routes/r.py": "from pkg.services import s\n",
        "factory.py": "from pkg.routes import r\nfrom pkg.repository import db\n",
    }
    assert all(v == [] for v in run(tmp_path, files).values())
