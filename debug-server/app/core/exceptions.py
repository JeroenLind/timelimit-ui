"""Custom exception classes for the debug server.

This module defines custom exception classes for various error conditions:
- AuthenticationError — 401 Unauthorized
- AuthorizationError — 403 Forbidden
- NotFoundError — 404 Not Found
- ConflictError — 409 Conflict
- RateLimitError — 429 Too Many Requests
- CryptoError — Encryption/decryption failures
- ValidationError — Input validation failures
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Exception for authentication failures (401 Unauthorized).

    Raised when:
    - Token is missing
    - Token is invalid
    - Token has expired
    - Credentials are invalid
    """

    def __init__(
        self,
        detail: str = "Authentication failed",
        headers: Optional[Dict[str, str]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers or {"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(HTTPException):
    """Exception for authorization failures (403 Forbidden).

    Raised when:
    - User is authenticated but lacks permission
    - Resource access is denied
    """

    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class NotFoundError(HTTPException):
    """Exception for resource not found (404 Not Found).

    Raised when:
    - Requested resource does not exist
    - Entity ID not found
    """

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class ConflictError(HTTPException):
    """Exception for conflicts (409 Conflict).

    Raised when:
    - Duplicate resource creation
    - Version conflict
    - State conflict
    """

    def __init__(self, detail: str = "Conflict occurred"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class GoneError(HTTPException):
    """Exception for resource gone (410 Gone).

    Raised when:
    - Resource no longer available
    - Resource permanently removed
    """

    def __init__(self, detail: str = "Resource no longer available"):
        super().__init__(
            status_code=status.HTTP_410_GONE,
            detail=detail
        )


class RateLimitError(HTTPException):
    """Exception for rate limiting (429 Too Many Requests).

    Raised when:
    - Rate limit exceeded
    - Too many requests in time window
    """

    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers=headers
        )


class BadRequestError(HTTPException):
    """Exception for bad requests (400 Bad Request).

    Raised when:
    - Invalid request format
    - Missing required fields
    - Invalid parameter values
    """

    def __init__(self, detail: str = "Bad request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class ValidationError(HTTPException):
    """Exception for validation failures (400 Bad Request).

    Raised when:
    - Input validation fails
    - Data does not match expected schema
    """

    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class CryptoError(HTTPException):
    """Exception for cryptographic failures (500 Internal Server Error).

    Raised when:
    - Encryption/decryption fails
    - Key operations fail
    - Signature verification fails
    """

    def __init__(self, detail: str = "Cryptographic operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class InternalServerError(HTTPException):
    """Exception for internal server errors (500 Internal Server Error).

    Raised when:
    - Unexpected errors occur
    - Server-side failures
    """

    def __init__(self, detail: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


# Exception handler for FastAPI
def create_exception_handlers():
    """Create exception handlers for FastAPI.

    Returns:
        A dictionary of exception handlers.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def authentication_exception_handler(
        request: Request,
        exc: AuthenticationError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail},
            headers=exc.headers
        )

    async def authorization_exception_handler(
        request: Request,
        exc: AuthorizationError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    async def not_found_exception_handler(
        request: Request,
        exc: NotFoundError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    async def conflict_exception_handler(
        request: Request,
        exc: ConflictError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    async def rate_limit_exception_handler(
        request: Request,
        exc: RateLimitError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail},
            headers=exc.headers
        )

    async def bad_request_exception_handler(
        request: Request,
        exc: BadRequestError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    async def validation_error_exception_handler(
        request: Request,
        exc: ValidationError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    async def crypto_error_exception_handler(
        request: Request,
        exc: CryptoError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    async def internal_server_error_exception_handler(
        request: Request,
        exc: InternalServerError
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": exc.detail}
        )

    return {
        AuthenticationError: authentication_exception_handler,
        AuthorizationError: authorization_exception_handler,
        NotFoundError: not_found_exception_handler,
        ConflictError: conflict_exception_handler,
        RateLimitError: rate_limit_exception_handler,
        BadRequestError: bad_request_exception_handler,
        ValidationError: validation_error_exception_handler,
        CryptoError: crypto_error_exception_handler,
        InternalServerError: internal_server_error_exception_handler,
    }