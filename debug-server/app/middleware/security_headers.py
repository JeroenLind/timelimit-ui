"""Security headers middleware.

This middleware adds security headers to all responses:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Content-Security-Policy: default-src 'none'
- Strict-Transport-Security (if HTTPS enabled)
- X-XSS-Protection: 1; mode=block
"""

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add security headers to the response.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response with security headers added.
        """
        response = await call_next(request)

        # Add X-Content-Type-Options header
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Add X-Frame-Options header
        response.headers["X-Frame-Options"] = "DENY"

        # Add Content-Security-Policy header
        response.headers["Content-Security-Policy"] = "default-src 'none'"

        # Add X-XSS-Protection header
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Add Strict-Transport-Security header if HTTPS is enabled
        if settings.ENABLE_HTTPS:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


def add_security_headers(response: Response) -> None:
    """Add security headers to a response object.

    Args:
        response: The response object to modify.
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    if settings.ENABLE_HTTPS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"