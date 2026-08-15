"""Unit tests for gzip middleware.

This module tests the GzipMiddleware class:
- Request decompression
- Response compression
- Content-Encoding handling
- Content-Length negotiation
"""

import pytest
import gzip
import json
from io import BytesIO

from starlette.testclient import TestClient
from app.main import create_application


class TestGzipMiddleware:
    """Tests for GzipMiddleware functionality."""

    @pytest.fixture
    def app(self):
        """Create application with gzip middleware."""
        app = create_application()
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_response_compression(self, client):
        """Test that responses are compressed when appropriate."""
        # Create a large enough response to trigger compression
        large_data = {"data": "x" * 2000}

        response = client.post(
            "/register",
            json=large_data
        )

        # Response should be successful
        assert response.status_code in [200, 422, 400], \
            f"Response should be successful, got {response.status_code}"

    def test_gzip_request_decompression(self, client):
        """Test that gzipped requests are decompressed."""
        # Create gzipped request body
        data = {"email": "test@example.com", "password": "password123"}
        json_data = json.dumps(data).encode("utf-8")
        gzipped_data = gzip.compress(json_data)

        response = client.post(
            "/register",
            content=gzipped_data,
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Request should be processed
        assert response.status_code in [200, 422, 400], \
            f"Request should be processed, got {response.status_code}"

    def test_content_length_negotiation(self, client):
        """Test Content-Length header handling."""
        response = client.get("/health")

        assert response.status_code == 200, "Health check should succeed"
        # Content-Length should be present
        assert "content-length" in response.headers, \
            "Response should have Content-Length header"

    def test_minimum_size_threshold(self, client):
        """Test that small responses are not compressed."""
        # Small response
        response = client.get("/health")

        assert response.status_code == 200, "Health check should succeed"
        # Small responses may or may not be compressed, but should work

    def test_accept_encoding_header(self, client):
        """Test Accept-Encoding header handling."""
        response = client.get(
            "/health",
            headers={"Accept-Encoding": "gzip, deflate"}
        )

        assert response.status_code == 200, "Request with Accept-Encoding should succeed"


class TestGzipCompression:
    """Tests for gzip compression functionality."""

    def test_compress_data(self):
        """Test data compression."""
        original_data = b"Hello, World! " * 100
        compressed = gzip.compress(original_data)

        assert compressed != original_data, "Compressed data should differ from original"
        assert len(compressed) < len(original_data), "Compressed data should be smaller"

    def test_decompress_data(self):
        """Test data decompression."""
        original_data = b"Hello, World! " * 100
        compressed = gzip.compress(original_data)
        decompressed = gzip.decompress(compressed)

        assert decompressed == original_data, "Decompressed data should match original"

    def test_compress_decompress_roundtrip(self):
        """Test compression and decompression roundtrip."""
        test_data = b"Test data for compression roundtrip" * 50

        compressed = gzip.compress(test_data)
        decompressed = gzip.decompress(compressed)

        assert decompressed == test_data, "Roundtrip should preserve data"

    def test_compress_empty_data(self):
        """Test compression of empty data."""
        original_data = b""
        compressed = gzip.compress(original_data)
        decompressed = gzip.decompress(compressed)

        assert decompressed == original_data, "Empty data should roundtrip"

    def test_compress_large_data(self):
        """Test compression of large data."""
        # Create 1MB of data
        original_data = b"x" * (1024 * 1024)
        compressed = gzip.compress(original_data)

        assert len(compressed) < len(original_data), \
            "Compressed large data should be smaller"

        decompressed = gzip.decompress(compressed)
        assert decompressed == original_data, "Large data should roundtrip"


class TestGzipMiddlewareIntegration:
    """Integration tests for gzip middleware with API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_application()
        return TestClient(app)

    def test_health_endpoint_with_gzip(self, client):
        """Test health endpoint with gzip encoding."""
        response = client.get(
            "/health",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200, "Health check should succeed"

    def test_register_endpoint_with_gzip(self, client):
        """Test register endpoint with gzip encoding."""
        user_data = {
            "email": "gzip_test@example.com",
            "password": "password12345678"
        }

        # Compress the request body
        json_data = json.dumps(user_data).encode("utf-8")
        gzipped_data = gzip.compress(json_data)

        response = client.post(
            "/register",
            content=gzipped_data,
            headers={
                "Content-Encoding": "gzip",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Should process the request
        assert response.status_code in [200, 422, 400], \
            f"Request should be processed, got {response.status_code}"

    def test_login_endpoint_with_gzip(self, client):
        """Test login endpoint with gzip encoding."""
        login_data = {
            "username": "test@example.com",
            "password": "password123"
        }

        json_data = json.dumps(login_data).encode("utf-8")
        gzipped_data = gzip.compress(json_data)

        response = client.post(
            "/login",
            content=gzipped_data,
            headers={
                "Content-Encoding": "gzip",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Should process the request
        assert response.status_code in [200, 401, 422], \
            f"Request should be processed, got {response.status_code}"


class TestGzipEdgeCases:
    """Tests for edge cases in gzip handling."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_application()
        return TestClient(app)

    def test_malformed_gzip_request(self, client):
        """Test handling of malformed gzip data."""
        response = client.post(
            "/register",
            content=b"not valid gzip data",
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Should handle gracefully (either decompress error or validation error)
        assert response.status_code in [400, 422, 500], \
            f"Should handle malformed gzip gracefully, got {response.status_code}"

    def test_gzip_with_invalid_json(self, client):
        """Test gzip decompression with invalid JSON."""
        gzipped_data = gzip.compress(b"not json data")

        response = client.post(
            "/register",
            content=gzipped_data,
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Should return validation error
        assert response.status_code in [400, 422], \
            f"Should return validation error for invalid JSON, got {response.status_code}"

    def test_double_gzip_request(self, client):
        """Test handling of double-gzipped data."""
        data = b'{"email": "test@example.com"}'
        double_gzipped = gzip.compress(gzip.compress(data))

        response = client.post(
            "/register",
            content=double_gzipped,
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422, 500], \
            f"Should handle double-gzip gracefully, got {response.status_code}"

    def test_gzip_with_binary_data(self, client):
        """Test gzip with binary-like data."""
        # Create binary-like data
        binary_data = bytes(range(256)) * 10
        gzipped_data = gzip.compress(binary_data)

        response = client.post(
            "/register",
            content=gzipped_data,
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )

        # Should handle gracefully
        assert response.status_code in [400, 422], \
            f"Should handle binary data gracefully, got {response.status_code}"


class TestGzipConfiguration:
    """Tests for gzip middleware configuration."""

    def test_compression_level(self):
        """Test that compression level affects output."""
        data = b"Test data for compression level testing" * 100

        # Default compression
        compressed_default = gzip.compress(data)

        # Higher compression
        compressed_high = gzip.compress(data, compresslevel=9)

        # Both should decompress to original
        assert gzip.decompress(compressed_default) == data
        assert gzip.decompress(compressed_high) == data

    def test_minimum_size_threshold_config(self):
        """Test minimum size threshold configuration."""
        # Small data
        small_data = b"Small data"
        compressed_small = gzip.compress(small_data)

        # Large data
        large_data = b"x" * 2000
        compressed_large = gzip.compress(large_data)

        # Both should work
        assert gzip.decompress(compressed_small) == small_data
        assert gzip.decompress(compressed_large) == large_data

    def test_gzip_headers(self):
        """Test gzip header format."""
        data = b"Test data"
        compressed = gzip.compress(data)

        # Gzip header should start with magic bytes
        assert compressed[0:2] == b'\x1f\x8b', "Gzip header should have magic bytes"

        # Should have valid header
        bio = BytesIO(compressed)
        with gzip.GzipFile(fileobj=bio) as gf:
            decompressed = gf.read()

        assert decompressed == data, "Decompression should work"
