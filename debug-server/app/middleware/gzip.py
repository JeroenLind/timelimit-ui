"""Gzip compression/decompression middleware.

This middleware handles:
- Decompressing incoming gzip request bodies
- Compressing outgoing gzip response bodies
- Handling Content-Encoding: gzip header
- Content-Length auto-negotiation (411 retry simulation)
"""

import gzip
import io
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class GzipMiddleware(BaseHTTPMiddleware):
    """Middleware for gzip compression and decompression."""

    def __init__(self, app, compress_level: int = 6, minimum_size: int = 1000):
        """Initialize the gzip middleware.

        Args:
            app: The FastAPI/Starlette application.
            compress_level: Gzip compression level (1-9, default 6).
            minimum_size: Minimum response size in bytes to compress (default 1000).
        """
        super().__init__(app)
        self.compress_level = compress_level
        self.minimum_size = minimum_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with gzip handling.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response, potentially with gzip compression applied.
        """
        # Handle incoming gzip-compressed request body
        if self._is_gzipped_request(request):
            request = await self._decompress_request_body(request)

        # Process the request
        response = await call_next(request)

        # Compress response if appropriate
        if self._should_compress_response(request, response):
            response = await self._compress_response(response)

        return response

    def _is_gzipped_request(self, request: Request) -> bool:
        """Check if the request has gzip encoding.

        Args:
            request: The HTTP request.

        Returns:
            True if the request is gzip-encoded.
        """
        content_encoding = request.headers.get("Content-Encoding", "")
        return content_encoding.lower() == "gzip"

    async def _decompress_request_body(self, request: Request) -> Request:
        """Decompress the request body.

        Args:
            request: The incoming HTTP request with gzip body.

        Returns:
            The request with decompressed body.
        """
        try:
            # Read the compressed body
            body = await request.body()

            # Decompress
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
                decompressed_body = gz.read()

            # Create a new request with decompressed body
            # We need to replace the body in the request scope
            new_request = Request(
                scope=request.scope,
                receive=self._create_receive(decompressed_body),
            )

            logger.debug(
                "Request body decompressed",
                extra={
                    "original_size": len(body),
                    "decompressed_size": len(decompressed_body),
                    "path": request.url.path,
                }
            )

            return new_request

        except Exception as e:
            logger.warning(
                "Failed to decompress request body",
                extra={
                    "error": str(e),
                    "path": request.url.path,
                }
            )
            # Return original request if decompression fails
            return request

    def _create_receive(self, body: bytes):
        """Create a receive callable with the given body.

        Args:
            body: The request body bytes.

        Returns:
            A receive callable that returns the body.
        """
        async def receive():
            return {"type": "http.request", "body": body}
        return receive

    def _should_compress_response(
        self, request: Request, response: Response
    ) -> bool:
        """Determine if the response should be compressed.

        Args:
            request: The HTTP request.
            response: The HTTP response.

        Returns:
            True if the response should be compressed.
        """
        # Check if client accepts gzip
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding.lower():
            return False

        # Check if response is already compressed
        content_encoding = response.headers.get("Content-Encoding", "")
        if content_encoding and content_encoding.lower() != "identity":
            return False

        # Check response status code
        if response.status_code < 200 or response.status_code >= 300:
            return False

        # Check if response has a body
        if not hasattr(response, "body") or response.body is None:
            return False

        # Check minimum size
        body_size = len(response.body) if isinstance(response.body, bytes) else 0
        if body_size < self.minimum_size:
            return False

        # Don't compress if Content-Type is already set to gzip
        content_type = response.headers.get("Content-Type", "")
        if "gzip" in content_type.lower():
            return False

        return True

    async def _compress_response(self, response: Response) -> Response:
        """Compress the response body.

        Args:
            response: The HTTP response to compress.

        Returns:
            The compressed response.
        """
        try:
            # Get the body
            body = response.body
            if not isinstance(body, bytes):
                body = body.encode("utf-8") if isinstance(body, str) else b""

            # Compress
            with io.BytesIO() as buf:
                with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=self.compress_level) as gz:
                    gz.write(body)
                compressed_body = buf.getvalue()

            # Update response
            response.body = compressed_body
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Content-Length"] = str(len(compressed_body))

            logger.debug(
                "Response body compressed",
                extra={
                    "original_size": len(body),
                    "compressed_size": len(compressed_body),
                    "compression_ratio": len(compressed_body) / len(body) if body else 0,
                }
            )

            return response

        except Exception as e:
            logger.warning(
                "Failed to compress response body",
                extra={
                    "error": str(e),
                }
            )
            return response


def get_gzip_middleware(
    compress_level: int = 6,
    minimum_size: int = 1000
) -> type:
    """Get the GzipMiddleware class with custom settings.

    Args:
        compress_level: Gzip compression level (1-9, default 6).
        minimum_size: Minimum response size in bytes to compress (default 1000).

    Returns:
        The GzipMiddleware class.
    """
    class CustomGzipMiddleware(GzipMiddleware):
        def __init__(self, app):
            super().__init__(app, compress_level, minimum_size)

    return CustomGzipMiddleware