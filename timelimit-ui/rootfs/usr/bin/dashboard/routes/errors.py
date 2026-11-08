"""One error envelope for every API route, and one request id per request (TR-307, plan A4).

Routes never build an error response by hand: they raise ``DashboardError`` (or call ``abort``) and the
handlers here answer ``{"status": "error", "code", "message", "requestId"}`` with the status of the
code. Unknown exceptions give ``INTERNAL_ERROR`` / 500 with a generic message and no stack trace; the
trace goes to the log together with the request id.
"""

from __future__ import annotations

import re
import time
import uuid

from flask import Flask, Response, g, jsonify, request
from werkzeug.exceptions import HTTPException

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.logs import fields, get_logger

API_PREFIX = "/api/"
REQUEST_ID_HEADER = "X-Request-ID"
GENERIC_MESSAGE = "Unexpected error. See the log with the request id."

HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.SESSION_INVALID: 401,
    ErrorCode.INVALID_PASSWORD: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.NOT_LINKED: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.READ_ONLY_OFFLINE: 503,
    ErrorCode.SERVER_UNREACHABLE: 502,
    ErrorCode.SERVER_TIMEOUT: 504,
    ErrorCode.ACTION_NOT_CONFIRMED: 502,
    ErrorCode.INTERNAL_ERROR: 500,
}

# Framework errors (unknown path, wrong method, bad body) -> our codes.
_HTTP_EXCEPTION_CODES = {
    400: ErrorCode.INVALID_INPUT,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.INVALID_INPUT,
    413: ErrorCode.INVALID_INPUT,
    415: ErrorCode.INVALID_INPUT,
}

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
log = get_logger("http")


def current_request_id() -> str:
    """The id of the running request (a fresh one outside a request context)."""
    return str(getattr(g, "request_id", None) or uuid.uuid4().hex)


def error_response(code: ErrorCode, message: str) -> Response:
    """The envelope for ``code``; the one place that builds an error body."""
    response = jsonify(
        {
            "status": "error",
            "code": code.value,
            "message": message,
            "requestId": current_request_id(),
        }
    )
    response.status_code = HTTP_STATUS[code]
    return response


def _is_api_request() -> bool:
    return request.path.startswith(API_PREFIX)


def register_error_handling(app: Flask) -> None:
    """Install the request id, the request log line and the error handlers on ``app``."""

    @app.before_request
    def _start_request() -> None:
        sent = request.headers.get(REQUEST_ID_HEADER, "")
        g.request_id = sent if _VALID_REQUEST_ID.match(sent) else uuid.uuid4().hex
        g.started = time.monotonic()

    @app.after_request
    def _finish_request(response: Response) -> Response:
        response.headers[REQUEST_ID_HEADER] = current_request_id()
        log.debug(
            "request",
            extra=fields(
                requestId=current_request_id(),
                method=request.method,
                path=request.path,
                status=response.status_code,
                ms=round(
                    (time.monotonic() - g.get("started", time.monotonic())) * 1000, 1
                ),
            ),
        )
        return response

    @app.errorhandler(DashboardError)
    def _dashboard_error(error: DashboardError) -> Response:
        status = HTTP_STATUS[error.code]
        log.log(
            40 if status >= 500 else 30,
            "request failed",
            extra=fields(
                requestId=current_request_id(), code=error.code.value, status=status
            ),
        )
        return error_response(error.code, error.message)

    @app.errorhandler(HTTPException)
    def _http_error(error: HTTPException) -> Response | HTTPException:
        if not _is_api_request():
            return error
        code = _HTTP_EXCEPTION_CODES.get(error.code or 500, ErrorCode.INTERNAL_ERROR)
        message = (
            GENERIC_MESSAGE
            if code is ErrorCode.INTERNAL_ERROR
            else (error.description or code.value)
        )
        log.warning(
            "request failed",
            extra=fields(
                requestId=current_request_id(),
                code=code.value,
                status=HTTP_STATUS[code],
            ),
        )
        return error_response(code, message)

    @app.errorhandler(Exception)
    def _unexpected(error: Exception) -> Response:
        log.error(
            "unexpected error",
            exc_info=error,
            extra=fields(
                requestId=current_request_id(), code=ErrorCode.INTERNAL_ERROR.value
            ),
        )
        return error_response(ErrorCode.INTERNAL_ERROR, GENERIC_MESSAGE)
