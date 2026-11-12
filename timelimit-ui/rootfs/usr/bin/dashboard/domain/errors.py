"""The fixed list of error codes and the one exception the layers below the routes raise (TR-307).

Services, repository and client raise ``DashboardError`` with a code; the routes layer turns it into
the error envelope ``{status: "error", code, message, requestId}`` (see ``routes/errors.py``).
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Every error the browser can get. The HTTP status of each code is fixed in design section 6."""

    INVALID_INPUT = "INVALID_INPUT"
    SESSION_INVALID = "SESSION_INVALID"
    INVALID_PASSWORD = "INVALID_PASSWORD"
    NOT_FOUND = "NOT_FOUND"
    NOT_LINKED = "NOT_LINKED"
    CONFLICT = "CONFLICT"
    READ_ONLY_OFFLINE = "READ_ONLY_OFFLINE"
    SERVER_UNREACHABLE = "SERVER_UNREACHABLE"
    SERVER_TIMEOUT = "SERVER_TIMEOUT"
    ACTION_NOT_CONFIRMED = "ACTION_NOT_CONFIRMED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DashboardError(Exception):
    """An error with one of the fixed codes and a message that is safe to show to the user."""

    def __init__(self, code: ErrorCode, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = (
            field  # the form field an INVALID_INPUT is about, when there is one
        )
