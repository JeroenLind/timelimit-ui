"""The ``Secret`` wrapper: tokens, hashes and typed passwords never show up by accident (TR-513).

``repr()``, ``str()``, ``format()`` and ``%`` all give a mask. The value is only available through
an explicit :meth:`Secret.reveal`, which the logging layer calls at debug level only (decision Q13).
"""

from __future__ import annotations

import hmac
from typing import Any

MASK = "***"

# Field names whose values are masked in log records (compared lower-case, without "_" and "-").
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "token",
        "authtoken",
        "deviceauthtoken",
        "accesstoken",
        "refreshtoken",
        "mailauthtoken",
        "maillogintoken",
        "password",
        "parentpassword",
        "newpassword",
        "oldpassword",
        "passwordhash",
        "parentpasswordhash",
        "parentpasswordsecondhash",
        "secondhash",
        "hash",
        "secret",
        "secretkey",
        "apikey",
        "privatekey",
        "signature",
        "credentials",
    }
)


def is_sensitive_field(name: str) -> bool:
    """True when a log field with this name must be masked."""
    return name.lower().replace("_", "").replace("-", "") in SENSITIVE_FIELD_NAMES


class Secret:
    """A string that hides itself. Compare with ``==``; read with :meth:`reveal`."""

    __slots__ = ("_value",)

    def __init__(self, value: str | Secret) -> None:
        raw: object = value.reveal() if isinstance(value, Secret) else value
        if not isinstance(raw, str):
            raise TypeError("Secret wraps a str")
        self._value = raw

    def reveal(self) -> str:
        """The real value. Call this only where it is really needed (HTTP header, hashing)."""
        return self._value

    def __repr__(self) -> str:
        return f"Secret({MASK})"

    def __str__(self) -> str:
        return MASK

    def __format__(self, format_spec: str) -> str:
        return format(MASK, format_spec)

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            return hmac.compare_digest(self._value.encode(), other._value.encode())
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Secret", self._value))

    def __reduce__(self) -> Any:
        raise TypeError("a Secret cannot be pickled or copied into another process")


def mask(value: object) -> str:
    """The mask for any value (used for sensitive log fields and strings)."""
    return MASK
