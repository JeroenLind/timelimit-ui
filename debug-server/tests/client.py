"""Test client for TimeLimit API.

This module provides a Python client for interacting with the test server
for automated testing.
"""

import gzip
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class TestClient:
    """Python test client for TimeLimit API.
    
    Provides methods for all API endpoints with:
    - Automatic gzip compression/decompression
    - JWT token management
    - Request/response logging
    - Assertion helpers
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: int = 30,
        verify_ssl: bool = True
    ):
        """Initialize the test client.
        
        Args:
            base_url: Base URL for the API server.
            timeout: Request timeout in seconds.
            verify_ssl: Whether to verify SSL certificates.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._token: Optional[str] = None
        self._device_token: Optional[str] = None
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify_ssl,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            }
        )
    
    def set_token(self, token: str) -> None:
        """Set the JWT token for authenticated requests.
        
        Args:
            token: JWT token string.
        """
        self._token = token
        self._client.headers["Authorization"] = f"Bearer {token}"
    
    def set_device_token(self, token: str) -> None:
        """Set the device auth token for authenticated requests.
        
        Args:
            token: Device auth token string.
        """
        self._device_token = token
        self._client.headers["X-Device-Auth-Token"] = token
    
    def clear_token(self) -> None:
        """Clear the JWT token."""
        self._token = None
        if "Authorization" in self._client.headers:
            del self._client.headers["Authorization"]
    
    def clear_device_token(self) -> None:
        """Clear the device auth token."""
        self._device_token = None
        if "X-Device-Auth-Token" in self._client.headers:
            del self._client.headers["X-Device-Auth-Token"]
    
    def _compress_body(self, data: Dict[str, Any]) -> bytes:
        """Compress request body using gzip.
        
        Args:
            data: Dictionary to compress.
            
        Returns:
            Compressed bytes.
        """
        json_data = json.dumps(data).encode("utf-8")
        return gzip.compress(json_data)
    
    def _decompress_response(self, content: bytes) -> bytes:
        """Decompress response body if gzipped.
        
        Args:
            content: Response content bytes.
            
        Returns:
            Decompressed bytes.
        """
        try:
            return gzip.decompress(content)
        except Exception:
            return content
    
    def _log_request(self, method: str, url: str, data: Any = None) -> None:
        """Log request details.
        
        Args:
            method: HTTP method.
            url: Request URL.
            data: Request data.
        """
        logger.debug(
            f"Request: {method} {url}",
            extra={"data": str(data)[:200]}
        )
    
    def _log_response(self, response: httpx.Response) -> None:
        """Log response details.
        
        Args:
            response: HTTP response.
        """
        logger.debug(
            f"Response: {response.status_code}",
            extra={"headers": dict(response.headers)}
        )
    
    # ========================================================================
    # Health Check Endpoints
    # ========================================================================
    
    def get_health(self) -> Dict[str, Any]:
        """GET /health - Health check endpoint."""
        response = self._client.get("/health")
        self._log_response(response)
        return response.json()
    
    def get_ready(self) -> Dict[str, Any]:
        """GET /ready - Readiness check endpoint."""
        response = self._client.get("/ready")
        self._log_response(response)
        return response.json()
    
    # ========================================================================
    # Auth Endpoints
    # ========================================================================
    
    def post_time(self) -> Dict[str, Any]:
        """POST /time - Get server time."""
        response = self._client.post("/time")
        self._log_response(response)
        return response.json()
    
    def send_mail_login_code(
        self,
        mail: str,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """POST /auth/send-mail-login-code-v2 - Send mail login code."""
        response = self._client.post(
            "/auth/send-mail-login-code-v2",
            json={"mail": mail, "locale": locale}
        )
        self._log_response(response)
        return response.json()
    
    def sign_in_by_mail_code(
        self,
        mail_login_token: str,
        received_code: str
    ) -> Dict[str, Any]:
        """POST /auth/sign-in-by-mail-code - Sign in by mail code."""
        response = self._client.post(
            "/auth/sign-in-by-mail-code",
            json={
                "mailLoginToken": mail_login_token,
                "receivedCode": received_code
            }
        )
        self._log_response(response)
        return response.json()
    
    def get_status_by_mail_address(
        self,
        mail_auth_token: str
    ) -> Dict[str, Any]:
        """POST /parent/get-status-by-mail-address - Get status by mail."""
        response = self._client.post(
            "/parent/get-status-by-mail-address",
            json={"mailAuthToken": mail_auth_token}
        )
        self._log_response(response)
        return response.json()
    
    def create_family(
        self,
        mail_auth_token: str,
        parent_password: Dict[str, str],
        device_name: str = "Test Device",
        device_model: str = "Pixel 7"
    ) -> Dict[str, Any]:
        """POST /parent/create-family - Create family."""
        response = self._client.post(
            "/parent/create-family",
            json={
                "mailAuthToken": mail_auth_token,
                "parentPassword": parent_password,
                "deviceName": device_name,
                "deviceModel": device_model
            }
        )
        self._log_response(response)
        return response.json()
    
    def sign_in_into_family(
        self,
        mail_auth_token: str,
        parent_password_second_hash: str,
        device_name: str = "Test Device",
        device_model: str = "Pixel 7"
    ) -> Dict[str, Any]:
        """POST /parent/sign-in-into-family - Sign in to family."""
        response = self._client.post(
            "/parent/sign-in-into-family",
            json={
                "mailAuthToken": mail_auth_token,
                "parentPasswordSecondHash": parent_password_second_hash,
                "deviceName": device_name,
                "deviceModel": device_model
            }
        )
        self._log_response(response)
        return response.json()
    
    def recover_parent_password(
        self,
        mail_auth_token: str,
        new_password: Dict[str, str]
    ) -> Dict[str, Any]:
        """POST /parent/recover-parent-password - Recover password."""
        response = self._client.post(
            "/parent/recover-parent-password",
            json={
                "mailAuthToken": mail_auth_token,
                "newPassword": new_password
            }
        )
        self._log_response(response)
        return response.json()
    
    # ========================================================================
    # Sync Endpoints
    # ========================================================================
    
    def push_actions(
        self,
        device_auth_token: str,
        actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """POST /sync/push-actions - Push actions."""
        response = self._client.post(
            "/sync/push-actions",
            json={
                "deviceAuthToken": device_auth_token,
                "actions": actions
            }
        )
        self._log_response(response)
        return response.json()
    
    def pull_status(
        self,
        device_auth_token: str,
        client_status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """POST /sync/pull-status - Pull status."""
        response = self._client.post(
            "/sync/pull-status",
            json={
                "deviceAuthToken": device_auth_token,
                "status": client_status
            }
        )
        self._log_response(response)
        return response.json()
    
    def report_removed(self, device_auth_token: str) -> Dict[str, Any]:
        """POST /sync/report-removed - Report device removed."""
        response = self._client.post(
            "/sync/report-removed",
            json={"deviceAuthToken": device_auth_token}
        )
        self._log_response(response)
        return response.json()
    
    def is_device_removed(self, device_auth_token: str) -> Dict[str, Any]:
        """POST /sync/is-device-removed - Check if device removed."""
        response = self._client.post(
            "/sync/is-device-removed",
            json={"deviceAuthToken": device_auth_token}
        )
        self._log_response(response)
        return response.json()
    
    # ========================================================================
    # Parent Endpoints
    # ========================================================================
    
    def create_add_device_token(
        self,
        device_auth_token: str,
        parent_id: str,
        parent_password_second_hash: str
    ) -> Dict[str, Any]:
        """POST /parent/create-add-device-token - Create add device token."""
        response = self._client.post(
            "/parent/create-add-device-token",
            json={
                "deviceAuthToken": device_auth_token,
                "parentId": parent_id,
                "parentPasswordSecondHash": parent_password_second_hash
            }
        )
        self._log_response(response)
        return response.json()
    
    def remove_device(
        self,
        device_auth_token: str,
        device_id: str
    ) -> Dict[str, Any]:
        """POST /parent/remove-device - Remove device."""
        response = self._client.post(
            "/parent/remove-device",
            json={
                "deviceAuthToken": device_auth_token,
                "deviceId": device_id
            }
        )
        self._log_response(response)
        return response.json()
    
    def link_mail_address(
        self,
        device_auth_token: str,
        mail_auth_token: str
    ) -> Dict[str, Any]:
        """POST /parent/link-mail-address - Link mail address."""
        response = self._client.post(
            "/parent/link-mail-address",
            json={
                "deviceAuthToken": device_auth_token,
                "mailAuthToken": mail_auth_token
            }
        )
        self._log_response(response)
        return response.json()
    
    def create_identity_token(self, device_auth_token: str) -> Dict[str, Any]:
        """POST /parent/create-identity-token - Create identity token."""
        response = self._client.post(
            "/parent/create-identity-token",
            json={"deviceAuthToken": device_auth_token}
        )
        self._log_response(response)
        return response.json()
    
    def delete_account(self, device_auth_token: str) -> Dict[str, Any]:
        """POST /parent/delete-account - Delete account."""
        response = self._client.post(
            "/parent/delete-account",
            json={"deviceAuthToken": device_auth_token}
        )
        self._log_response(response)
        return response.json()
    
    # ========================================================================
    # Child Endpoints
    # ========================================================================
    
    def add_device(
        self,
        register_token: str,
        device_name: str = "Child Device",
        device_model: str = "Pixel 7"
    ) -> Dict[str, Any]:
        """POST /child/add-device - Add device."""
        response = self._client.post(
            "/child/add-device",
            json={
                "registerToken": register_token,
                "deviceName": device_name,
                "deviceModel": device_model
            }
        )
        self._log_response(response)
        return response.json()
    
    def update_primary_device(
        self,
        device_auth_token: str,
        primary_device_id: str
    ) -> Dict[str, Any]:
        """POST /child/update-primary-device - Update primary device."""
        response = self._client.post(
            "/child/update-primary-device",
            json={
                "deviceAuthToken": device_auth_token,
                "primaryDeviceId": primary_device_id
            }
        )
        self._log_response(response)
        return response.json()
    
    def logout_at_primary_device(self, device_auth_token: str) -> Dict[str, Any]:
        """POST /child/logout-at-primary-device - Logout at primary device."""
        response = self._client.post(
            "/child/logout-at-primary-device",
            json={"deviceAuthToken": device_auth_token}
        )
        self._log_response(response)
        return response.json()
    
    # ========================================================================
    # Purchase Endpoints
    # ========================================================================
    
    def can_do_purchase(
        self,
        device_auth_token: str,
        product_id: str
    ) -> Dict[str, Any]:
        """POST /purchase/can-do-purchase - Check purchase eligibility."""
        response = self._client.post(
            "/purchase/can-do-purchase",
            json={
                "deviceAuthToken": device_auth_token,
                "productId": product_id
            }
        )
        self._log_response(response)
        return response.json()
    
    def finish_purchase_by_google_play(
        self,
        device_auth_token: str,
        product_id: str,
        purchase_token: str,
        signature: str
    ) -> Dict[str, Any]:
        """POST /purchase/finish-purchase-by-google-play - Finish purchase."""
        response = self._client.post(
            "/purchase/finish-purchase-by-google-play",
            json={
                "deviceAuthToken": device_auth_token,
                "productId": product_id,
                "purchaseToken": purchase_token,
                "signature": signature
            }
        )
        self._log_response(response)
        return response.json()
    
    # ========================================================================
    # Assertion Helpers
    # ========================================================================
    
    def assert_status(self, response: Dict[str, Any], expected: int) -> None:
        """Assert response status code.
        
        Args:
            response: Response dictionary.
            expected: Expected status code.
        """
        actual = response.get("status_code", 200)
        assert actual == expected, f"Expected status {expected}, got {actual}"
    
    def assert_status_ok(self, response: Dict[str, Any]) -> None:
        """Assert response status is 'ok'.
        
        Args:
            response: Response dictionary.
        """
        assert response.get("status") == "ok", f"Expected status 'ok', got {response.get('status')}"
    
    def assert_status_error(self, response: Dict[str, Any]) -> None:
        """Assert response status is 'error'.
        
        Args:
            response: Response dictionary.
        """
        assert response.get("status") == "error", f"Expected status 'error', got {response.get('status')}"
    
    def assert_has_field(self, response: Dict[str, Any], field: str) -> None:
        """Assert response has a field.
        
        Args:
            response: Response dictionary.
            field: Field name.
        """
        assert field in response, f"Response missing field: {field}"
    
    def assert_not_empty(self, value: Any, field: str = "value") -> None:
        """Assert value is not empty.
        
        Args:
            value: Value to check.
            field: Field name for error message.
        """
        assert value, f"{field} should not be empty"
    
    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self) -> "TestClient":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# Convenience function to create a test client
def create_test_client(base_url: str = "http://localhost:8080") -> TestClient:
    """Create a test client instance.
    
    Args:
        base_url: Base URL for the API server.
        
    Returns:
        TestClient instance.
    """
    return TestClient(base_url=base_url)