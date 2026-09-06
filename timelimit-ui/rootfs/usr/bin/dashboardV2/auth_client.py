"""Standalone HTTP client for debug-server API communication.

This module provides a standalone HTTP client for communicating with the
debug-server's /api/v1/ endpoints. It is completely self-contained and
does not import any debug-server internals.

All API calls use the Authorization: Bearer <token> header for authentication.
"""

import gzip
import html
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from config import Config
from middleware.request_logging import get_request_id
from utils.logging import get_logger
from utils.sanitization import SENSITIVE_KEYS, sanitize_dict
from utils.audit_log import (
    log_device_removal_request as audit_log_device_removal_request,
    log_device_removal_response as audit_log_device_removal_response,
    log_password_recovery_request as audit_log_password_recovery_request,
    log_password_recovery_response as audit_log_password_recovery_response,
    log_password_recovery_failure as audit_log_password_recovery_failure,
    log_sync_pull_request as audit_log_sync_pull_request,
    log_sync_pull_response as audit_log_sync_pull_response,
    log_sync_push_request as audit_log_sync_push_request,
    log_sync_push_response as audit_log_sync_push_response,
    log_family_creation_request as audit_log_family_creation_request,
    log_family_creation_response as audit_log_family_creation_response,
    log_family_creation_failure as audit_log_family_creation_failure
)

logger = get_logger(__name__)


def extract_error_from_html(response_content: bytes) -> Optional[str]:
    """Extract error message from HTML error response.
    
    Some servers return HTML error pages instead of JSON. This function
    extracts the error message from the HTML content.
    
    Args:
        response_content: Raw response content (bytes).
        
    Returns:
        Extracted error message or None if not found.
    """
    try:
        # Decode bytes to string
        if isinstance(response_content, bytes):
            content = response_content.decode('utf-8', errors='replace')
        else:
            content = str(response_content)
        
        # Try to extract error from <pre> tag (common in error pages)
        pre_match = re.search(r'<pre>(.*?)</pre>', content, re.DOTALL)
        if pre_match:
            error_text = pre_match.group(1)
            # Unescape HTML entities
            error_text = html.unescape(error_text)
            # Clean up whitespace
            error_text = ' '.join(error_text.split())
            return error_text
        
        # Try to extract error from <title> tag
        title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
        if title_match:
            return title_match.group(1).strip()
        
        return None
    except Exception:
        return None


@dataclass
class APIResponse:
    """Response from an API call.
    
    Attributes:
        success: Whether the request was successful.
        status_code: HTTP status code.
        data: Response data (parsed JSON or raw bytes).
        error_code: Error code if failed.
        error_message: Error message if failed.
        technical_detail: Technical details for debugging.
    """
    success: bool
    status_code: int
    data: Any
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    technical_detail: Optional[str] = None


class AuthClient:
    """HTTP client for debug-server API communication.
    
    This client provides methods for all authentication-related API endpoints
    and handles request formatting, error handling, and structured logging.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        verbose: bool = False
    ):
        """Initialize the auth client.
        
        Args:
            base_url: Base URL for the debug-server. Uses config default if not provided.
            timeout: Request timeout in seconds. Uses config default if not provided.
            max_retries: Maximum number of retries. Uses config default if not provided.
            retry_delay: Delay between retries in seconds. Uses config default if not provided.
            verbose: Enable verbose logging.
        """
        config = Config()
        self.base_url = (base_url or config.DEBUG_SERVER_URL).rstrip('/')
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.max_retries = max_retries or config.MAX_RETRIES
        self.retry_delay = retry_delay or config.RETRY_DELAY
        self.verbose = verbose
        self.session = requests.Session()
    
    def _get_headers(
        self,
        token: Optional[str] = None,
        content_type: str = 'application/json'
    ) -> Dict[str, str]:
        """Get request headers.
        
        Args:
            token: Optional Bearer token for authorization.
            content_type: Content-Type header value.
            
        Returns:
            Dictionary of headers.
        """
        headers = {'Content-Type': content_type}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        # Propagate X-Request-ID header for request tracing
        request_id = get_request_id()
        if request_id:
            headers['X-Request-ID'] = request_id
        
        return headers
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        retry_count: int = 0,
        skip_prefix: bool = False,
        gzip_compress: bool = False
    ) -> APIResponse:
        """Make an HTTP request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            data: Request body data.
            token: Optional Bearer token.
            retry_count: Current retry count.
            skip_prefix: If True, skip the API_PREFIX (for endpoints like /time).
            gzip_compress: If True, gzip-compress the request body.
            
        Returns:
            APIResponse object.
        """
        config = Config()
        if skip_prefix:
            url = f"{self.base_url}{endpoint}"
        else:
            url = f"{self.base_url}{config.API_PREFIX}{endpoint}"
        headers = self._get_headers(token)
        request_id = get_request_id()
        
        # Sanitize request data for logging
        sanitized_data = sanitize_dict(data) if data else None
        
        # Log request start with headers for debugging
        # Sanitize the Authorization header value for logging (show only first 8 chars)
        auth_header_value = headers.get('Authorization', '')
        if auth_header_value:
            auth_header_sanitized = auth_header_value[:8] + '...' if len(auth_header_value) > 8 else '***'
        else:
            auth_header_sanitized = None
        
        # Log full request details for debugging
        logger.debug(
            "Making API request",
            request_id=request_id,
            method=method,
            url=url,
            endpoint=endpoint,
            data=sanitized_data,
            retry_count=retry_count,
            gzip_compress=gzip_compress,
            has_auth_header='Authorization' in headers,
            auth_header_present=bool(token),
            auth_header_value=auth_header_sanitized,
            all_headers={k: v for k, v in headers.items() if k.lower() != 'authorization' or True}  # Include auth header for debugging
        )
        
        try:
            if method.upper() == 'POST':
                if gzip_compress:
                    # Gzip-compress the JSON body
                    json_body = json.dumps(data)
                    gzipped_body = gzip.compress(json_body.encode('utf-8'))
                    headers['Content-Encoding'] = 'gzip'
                    headers['Content-Length'] = str(len(gzipped_body))
                    response = self.session.post(
                        url,
                        data=gzipped_body,
                        headers=headers,
                        timeout=self.timeout
                    )
                else:
                    response = self.session.post(
                        url,
                        json=data,
                        headers=headers,
                        timeout=self.timeout
                    )
            elif method.upper() == 'GET':
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Parse response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = response.content
            
            # Sanitize response data for logging
            sanitized_response = sanitize_dict(response_data) if isinstance(response_data, dict) else response_data
            
            if response.ok:
                # Log successful response
                logger.info(
                    "API request successful",
                    request_id=request_id,
                    method=method,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    data=sanitized_response
                )
                
                return APIResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response_data
                )
            else:
                # Try to extract error details from response
                error_code = None
                error_message = None
                technical_detail = None
                
                if isinstance(response_data, dict):
                    error_code = response_data.get('error_code')
                    error_message = response_data.get('error_message') or response_data.get('detail')
                    technical_detail = response_data.get('technical_detail')
                elif isinstance(response_data, bytes):
                    # Try to extract error from HTML response
                    html_error = extract_error_from_html(response_data)
                    if html_error:
                        error_message = html_error
                        # Set error_code based on status code
                        if response.status_code == 409:
                            error_code = 'conflict'
                        elif response.status_code == 401:
                            error_code = 'unauthorized'
                        elif response.status_code == 400:
                            error_code = 'validation'
                        elif response.status_code >= 500:
                            error_code = 'server_error'
                        else:
                            error_code = 'http_error'
                
                # Log failed response
                logger.warning(
                    "API request failed",
                    request_id=request_id,
                    method=method,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    error_code=error_code,
                    error_message=error_message,
                    data=sanitized_response
                )
                
                return APIResponse(
                    success=False,
                    status_code=response.status_code,
                    data=response_data,
                    error_code=error_code,
                    error_message=error_message,
                    technical_detail=technical_detail
                )
                
        except requests.exceptions.Timeout:
            # Log timeout error
            logger.warning(
                "API request timeout",
                request_id=request_id,
                method=method,
                endpoint=endpoint,
                timeout_seconds=self.timeout,
                error_code='timeout'
            )
            
            return APIResponse(
                success=False,
                status_code=0,
                data=None,
                error_code='timeout',
                error_message='Request timed out',
                technical_detail=f'Connection timeout after {self.timeout} seconds'
            )
            
        except requests.exceptions.ConnectionError as e:
            # Log connection error
            logger.error(
                "API request connection error",
                request_id=request_id,
                method=method,
                endpoint=endpoint,
                error=str(e),
                error_code='unreachable'
            )
            
            return APIResponse(
                success=False,
                status_code=0,
                data=None,
                error_code='unreachable',
                error_message='Cannot connect to server',
                technical_detail=str(e)
            )
            
        except requests.exceptions.RequestException as e:
            # Log request error
            logger.error(
                "API request error",
                request_id=request_id,
                method=method,
                endpoint=endpoint,
                error=str(e),
                error_code='unknown'
            )
            
            return APIResponse(
                success=False,
                status_code=0,
                data=None,
                error_code='unknown',
                error_message='Request failed',
                technical_detail=str(e)
            )
    
    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        skip_prefix: bool = False,
        gzip_compress: bool = False
    ) -> APIResponse:
        """Make a request with retry logic.
        
        Args:
            method: HTTP method.
            endpoint: API endpoint path.
            data: Request body data.
            token: Optional Bearer token.
            skip_prefix: If True, skip the API_PREFIX (for endpoints like /time).
            gzip_compress: If True, gzip-compress the request body.
            
        Returns:
            APIResponse object.
        """
        last_error: Optional[APIResponse] = None
        
        for attempt in range(self.max_retries):
            response = self._make_request(
                method, endpoint, data, token, 
                retry_count=attempt, skip_prefix=skip_prefix,
                gzip_compress=gzip_compress
            )
            
            if response.success:
                return response
            
            last_error = response
            
            # Don't retry on certain errors
            if response.error_code in ['timeout', 'unreachable']:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.debug(
                        "Retrying request after error",
                        request_id=get_request_id(),
                        endpoint=endpoint,
                        attempt=attempt + 1,
                        delay_seconds=delay
                    )
                    time.sleep(delay)
                continue
            
            # For other errors, don't retry
            break
        
        return last_error or APIResponse(
            success=False,
            status_code=0,
            data=None,
            error_code='unknown',
            error_message='Request failed after retries'
        )
    
    # ========================================================================
    # Time Endpoint
    # ========================================================================
    
    def get_server_time(self) -> APIResponse:
        """Get server time from the debug-server.
        
        Returns:
            APIResponse with server time in milliseconds.
        """
        request_id = get_request_id()
        
        logger.debug(
            "Getting server time",
            request_id=request_id,
            base_url=self.base_url
        )
        
        response = self._request_with_retry('GET', '/time', skip_prefix=True)
        
        if response.success:
            logger.info(
                "Server time retrieved successfully",
                request_id=request_id,
                server_time=response.data.get('ms') if isinstance(response.data, dict) else None
            )
        else:
            logger.error(
                "Failed to retrieve server time",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Mail Login Code Endpoints
    # ========================================================================
    
    def send_mail_login_code(
        self,
        mail: str,
        locale: str,
        device_auth_token: Optional[str] = None
    ) -> APIResponse:
        """Send a mail login code to the specified email.
        
        Args:
            mail: Email address to send code to.
            locale: Locale string (required by server).
            device_auth_token: Optional existing device auth token.
            
        Returns:
            APIResponse with mailLoginToken.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        data = {'mail': mail, 'locale': locale}
        if device_auth_token:
            data['deviceAuthToken'] = device_auth_token
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Sending mail login code",
            request_id=request_id,
            mail=mail,
            locale=locale,
            has_device_auth_token=device_auth_token is not None
        )
        
        response = self._request_with_retry('POST', '/auth/send-mail-login-code-v2', data)
        
        if response.success:
            logger.info(
                "Mail login code sent successfully",
                request_id=request_id,
                mail=mail
            )
        else:
            logger.warning(
                "Failed to send mail login code",
                request_id=request_id,
                mail=mail,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    def sign_in_by_mail_code(
        self,
        mail_login_token: str,
        received_code: str
    ) -> APIResponse:
        """Sign in using a mail login token and verification code.
        
        Args:
            mail_login_token: Token from send_mail_login_code.
            received_code: Verification code received by email.
            
        Returns:
            APIResponse with mailAuthToken.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        data = {
            'mailLoginToken': mail_login_token,
            'receivedCode': received_code
        }
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Signing in by mail code",
            request_id=request_id
        )
        
        response = self._request_with_retry('POST', '/auth/sign-in-by-mail-code', data)
        
        if response.success:
            logger.info(
                "Sign in by mail code successful",
                request_id=request_id
            )
        else:
            logger.warning(
                "Failed to sign in by mail code",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Parent Status Endpoints
    # ========================================================================
    
    def get_status_by_mail_address(
        self,
        mail_auth_token: str
    ) -> APIResponse:
        """Get family status by mail auth token.
        
        Args:
            mail_auth_token: Mail auth token from sign-in.
            
        Returns:
            APIResponse with family status information.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        data = {'mailAuthToken': mail_auth_token}
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Getting status by mail address",
            request_id=request_id
        )
        
        response = self._request_with_retry('POST', '/parent/get-status-by-mail-address', data)
        
        if response.success:
            logger.info(
                "Status retrieved successfully",
                request_id=request_id
            )
        else:
            logger.warning(
                "Failed to get status by mail address",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Family Creation Endpoints
    # ========================================================================
    
    def create_family(
        self,
        mail_auth_token: str,
        parent_password: Dict[str, Any],
        parent_device: Dict[str, str],
        device_name: str,
        time_zone: str,
        parent_name: str,
        locale: Optional[str] = None,
        email: Optional[str] = None
    ) -> APIResponse:
        """Create a new family.
        
        Args:
            mail_auth_token: Mail auth token from sign-in.
            parent_password: Password data with hash, secondHash, secondSalt.
            parent_device: Device info dict with 'model' key.
            device_name: Device name (required).
            time_zone: Time zone string (required).
            parent_name: Parent name (required).
            locale: Optional locale string (not sent to server, kept for API compatibility).
            email: Optional email address (for audit logging).
            
        Returns:
            APIResponse with deviceAuthToken and ownDeviceId.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        # Note: locale is NOT included in the request body as it's not part of the server schema
        data = {
            'mailAuthToken': mail_auth_token,
            'parentPassword': parent_password,
            'parentDevice': parent_device,
            'deviceName': device_name,
            'timeZone': time_zone,
            'parentName': parent_name,
            'clientLevel': 7  # Matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
        }
        sanitized_data = sanitize_dict(data)
        
        # Log the request to audit log with complete fidelity (including password data)
        audit_log_family_creation_request(
            mail_auth_token=mail_auth_token,
            email=email,
            password_data=parent_password,
            parent_device=parent_device,
            device_name=device_name,
            time_zone=time_zone,
            parent_name=parent_name,
            locale=locale,
            request_id=request_id,
            server_url=self.base_url
        )
        
        logger.info(
            "Creating family",
            request_id=request_id,
            locale=locale,
            device_name=device_name,
            time_zone=time_zone,
            parent_name=parent_name,
            has_parent_password_hash=bool(parent_password.get('secondHash')) if parent_password else False,
            parent_password_keys=list(parent_password.keys()) if parent_password else []
        )
        
        response = self._request_with_retry('POST', '/parent/create-family', data)
        
        # Log the response to audit log
        audit_log_family_creation_response(
            success=response.success,
            request_id=request_id,
            status_code=response.status_code,
            response_data=response.data,
            error_code=response.error_code,
            error_message=response.error_message
        )
        
        if response.success:
            logger.info(
                "Family created successfully",
                request_id=request_id,
                has_device_auth_token=bool(response.data.get('deviceAuthToken')) if isinstance(response.data, dict) else False,
                has_own_device_id=bool(response.data.get('ownDeviceId')) if isinstance(response.data, dict) else False,
                device_auth_token_preview=response.data.get('deviceAuthToken', '')[:8] + '...' if isinstance(response.data, dict) and response.data.get('deviceAuthToken') else None
            )
        else:
            logger.warning(
                "Failed to create family",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message,
                status_code=response.status_code
            )
        
        return response
    
    def create_family_rest(
        self,
        mail_auth_token: str,
        parent_password: Dict[str, Any],
        parent_device: Dict[str, str],
        device_name: str,
        time_zone: str,
        parent_name: str,
        locale: Optional[str] = None,
        email: Optional[str] = None
    ) -> APIResponse:
        """Create a new family via RESTful endpoint.
        
        This is a RESTful alias for create_family() that proxies to the
        debug-server's /parent/create-family endpoint.
        
        Args:
            mail_auth_token: Mail auth token from sign-in.
            parent_password: Password data with hash, secondHash, secondSalt.
            parent_device: Device info dict with 'model' key.
            device_name: Device name (required).
            time_zone: Time zone string (required).
            parent_name: Parent name (required).
            locale: Optional locale string (not sent to server, kept for API compatibility).
            email: Optional email address (for audit logging).
            
        Returns:
            APIResponse with deviceAuthToken and ownDeviceId.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        # Note: locale is NOT included in the request body as it's not part of the server schema
        data = {
            'mailAuthToken': mail_auth_token,
            'parentPassword': parent_password,
            'parentDevice': parent_device,
            'deviceName': device_name,
            'timeZone': time_zone,
            'parentName': parent_name,
            'clientLevel': 7  # Matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
        }
        sanitized_data = sanitize_dict(data)
        
        # Log the request to audit log with complete fidelity (including password data)
        audit_log_family_creation_request(
            mail_auth_token=mail_auth_token,
            email=email,
            password_data=parent_password,
            parent_device=parent_device,
            device_name=device_name,
            time_zone=time_zone,
            parent_name=parent_name,
            locale=locale,
            request_id=request_id,
            server_url=self.base_url
        )
        
        logger.info(
            "Creating family (REST endpoint)",
            request_id=request_id,
            locale=locale,
            device_name=device_name,
            time_zone=time_zone,
            parent_name=parent_name
        )
        
        response = self._request_with_retry('POST', '/parent/create-family', data)
        
        # Log the response to audit log
        audit_log_family_creation_response(
            success=response.success,
            request_id=request_id,
            status_code=response.status_code,
            response_data=response.data,
            error_code=response.error_code,
            error_message=response.error_message
        )
        
        if response.success:
            logger.info(
                "Family created successfully (REST endpoint)",
                request_id=request_id,
                has_device_auth_token=bool(response.data.get('deviceAuthToken')) if isinstance(response.data, dict) else False
            )
        else:
            logger.warning(
                "Failed to create family (REST endpoint)",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response

    def sign_in_into_family(
        self,
        mail_auth_token: str,
        parent_password_second_hash: Optional[str] = None,
        locale: Optional[str] = None,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None,
        client_level: Optional[int] = None
    ) -> APIResponse:
        """Sign in to an existing family.
        
        Args:
            mail_auth_token: Mail auth token from sign-in.
            parent_password_second_hash: Optional second password hash (not required for email-based sign-in).
            locale: Optional locale string.
            device_name: Device name.
            device_model: Device model.
            client_level: Optional client level/version.
            
        Returns:
            APIResponse with deviceAuthToken and ownDeviceId.
        """
        request_id = get_request_id()
        
        # Build request data - parentDevice is required with model field
        data = {
            'mailAuthToken': mail_auth_token,
            'parentDevice': {'model': device_model} if device_model else {'model': 'Unknown'},
            'deviceName': device_name or 'Unknown Device'
        }
        
        # clientLevel is optional
        if client_level:
            data['clientLevel'] = client_level
        
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Signing in to family",
            request_id=request_id,
            locale=locale,
            has_device_name=device_name is not None,
            has_device_model=device_model is not None,
            has_client_level=client_level is not None
        )
        
        response = self._request_with_retry('POST', '/parent/sign-in-into-family', data)
        
        if response.success:
            logger.info(
                "Sign in to family successful",
                request_id=request_id,
                has_device_auth_token=bool(response.data.get('deviceAuthToken')) if isinstance(response.data, dict) else False
            )
        else:
            logger.warning(
                "Failed to sign in to family",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Parent Device Token Endpoints
    # ========================================================================
    
    def create_add_device_token(
        self,
        device_auth_token: str,
        parent_password_second_hash: str
    ) -> APIResponse:
        """Create an add-device token for a child device.
        
        Args:
            device_auth_token: Device auth token for authentication.
            parent_password_second_hash: Parent password second hash for verification.
            
        Returns:
            APIResponse with token and deviceId.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        data = {
            'deviceAuthToken': device_auth_token,
            'parentPasswordSecondHash': parent_password_second_hash
        }
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Creating add device token",
            request_id=request_id
        )
        
        response = self._request_with_retry(
            'POST',
            '/parent/create-add-device-token',
            data,
            token=device_auth_token
        )
        
        if response.success:
            logger.info(
                "Add device token created successfully",
                request_id=request_id,
                has_token=bool(response.data.get('token')) if isinstance(response.data, dict) else False
            )
        else:
            logger.warning(
                "Failed to create add device token",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Child Device Endpoints
    # ========================================================================
    
    def add_device(
        self,
        register_token: str,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None,
        client_level: Optional[int] = None
    ) -> APIResponse:
        """Register a child device.
        
        Args:
            register_token: Add-device token from parent.
            device_name: Optional device name.
            device_model: Optional device model.
            client_level: Optional client level/version.
            
        Returns:
            APIResponse with deviceAuthToken and ownDeviceId.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging
        data = {'registerToken': register_token}
        if device_name:
            data['deviceName'] = device_name
        if device_model:
            data['deviceModel'] = device_model
        if client_level:
            data['clientLevel'] = client_level
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Adding device",
            request_id=request_id,
            has_device_name=device_name is not None,
            has_device_model=device_model is not None,
            has_client_level=client_level is not None
        )
        
        response = self._request_with_retry('POST', '/child/add-device', data)
        
        if response.success:
            logger.info(
                "Device added successfully",
                request_id=request_id,
                has_device_auth_token=bool(response.data.get('deviceAuthToken')) if isinstance(response.data, dict) else False
            )
        else:
            logger.warning(
                "Failed to add device",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Password Recovery Endpoints
    # ========================================================================
    
    def recover_parent_password(
        self,
        mail_auth_token: str,
        new_password: Dict[str, Any]
    ) -> APIResponse:
        """Recover parent password.
        
        Args:
            mail_auth_token: Mail auth token from sign-in.
            new_password: New password data with hash, secondHash, secondSalt, encrypted.
            
        Returns:
            APIResponse with status.
        """
        request_id = get_request_id()
        
        # Prepare request data (not sanitized for audit logging)
        data = {
            'mailAuthToken': mail_auth_token,
            'password': new_password
        }
        
        logger.info(
            "Recovering parent password",
            request_id=request_id
        )
        
        # Log the request to audit log (with full password data)
        audit_log_password_recovery_request(
            mail_auth_token=mail_auth_token,
            password_data=new_password,
            request_id=request_id,
            server_url=self.base_url
        )
        
        response = self._request_with_retry('POST', '/parent/recover-parent-password', data)
        
        if response.success:
            logger.info(
                "Parent password recovered successfully",
                request_id=request_id
            )
            
            # Log the successful response to audit log
            audit_log_password_recovery_response(
                success=True,
                request_id=request_id,
                status_code=response.status_code,
                response_data=response.data
            )
        else:
            logger.warning(
                "Failed to recover parent password",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
            
            # Log the failure to audit log
            audit_log_password_recovery_failure(
                error_type='server_error',
                error_message=response.error_message or 'Unknown error',
                mail_auth_token=mail_auth_token,
                password_data=new_password,
                request_id=request_id
            )
        
        return response
    
    # ========================================================================
    # Sync Protocol Endpoints
    # ========================================================================
    
    def pull_status(
        self,
        device_auth_token: str,
        client_data_status: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """Pull server status (devices, users, categories) from the TimeLimit server.
        
        Args:
            device_auth_token: Device auth token for authentication.
            client_data_status: Client sync state (version numbers). If None,
                               an empty status is sent for initial full sync.
            
        Returns:
            APIResponse with ServerDataStatus data.
        """
        request_id = get_request_id()
        
        # Build ClientDataStatus - empty for initial sync
        # Format matches Android app's ClientDataStatus.empty (devices and users as empty strings,
        # optional fields omitted when not present)
        if client_data_status is None:
            client_data_status = {
                "clientLevel": 7,
                "devices": "",
                "users": "",
                "apps": {},
                "categories": {}
            }
        
        data = {
            "deviceAuthToken": device_auth_token,
            "status": client_data_status
        }
        
        # Log the pull request to audit log
        audit_log_sync_pull_request(
            device_auth_token=device_auth_token,
            client_data_status=client_data_status,
            request_id=request_id,
            server_url=self.base_url
        )
        
        logger.info(
            "Pulling server status",
            request_id=request_id,
            has_device_auth_token=True
        )
        
        response = self._request_with_retry(
            'POST',
            '/sync/pull-status',
            data,
            gzip_compress=True
        )
        
        # Log the response to audit log
        audit_log_sync_pull_response(
            device_auth_token=device_auth_token,
            request_id=request_id,
            success=response.success,
            status_code=response.status_code,
            response_data=response.data,
            error_code=response.error_code,
            error_message=response.error_message
        )
        
        if response.success:
            logger.info(
                "Server status pulled successfully",
                request_id=request_id,
                has_devices=isinstance(response.data, dict) and 'devices' in response.data,
                has_users=isinstance(response.data, dict) and 'users' in response.data
            )
        else:
            logger.warning(
                "Failed to pull server status",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    def push_actions(
        self,
        device_auth_token: str,
        actions: List[Dict[str, Any]]
    ) -> APIResponse:
        """Push pending actions to the server.
        
        Args:
            device_auth_token: Device auth token for authentication.
            actions: List of action objects with encodedAction, sequenceNumber,
                     integrity, type, and userId fields.
            
        Returns:
            APIResponse with shouldDoFullSync flag.
        """
        request_id = get_request_id()
        
        # Sanitize request data for logging (remove sensitive fields)
        sanitized_actions = []
        for action in actions:
            sanitized_action = {
                'type': action.get('type'),
                'userId': action.get('userId'),
                'sequenceNumber': action.get('sequenceNumber')
            }
            sanitized_actions.append(sanitized_action)
        
        data = {
            'deviceAuthToken': device_auth_token,
            'actions': actions
        }
        
        # Log the push request to audit log
        audit_log_sync_push_request(
            device_auth_token=device_auth_token,
            actions=actions,
            request_id=request_id,
            server_url=self.base_url
        )
        
        logger.info(
            "Pushing actions to server",
            request_id=request_id,
            has_device_auth_token=True,
            actions_count=len(actions),
            actions_preview=sanitized_actions[:5]  # Log first 5 actions for debugging
        )
        
        # Batch actions in groups of 25 as per the Android app implementation
        # For now, we send all actions in a single request
        response = self._request_with_retry(
            'POST',
            '/sync/push-actions',
            data,
            token=device_auth_token,
            gzip_compress=True
        )
        
        # Log the response to audit log
        audit_log_sync_push_response(
            device_auth_token=device_auth_token,
            request_id=request_id,
            success=response.success,
            status_code=response.status_code,
            response_data=response.data,
            error_code=response.error_code,
            error_message=response.error_message
        )
        
        if response.success:
            logger.info(
                "Actions pushed successfully",
                request_id=request_id,
                actions_count=len(actions)
            )
        else:
            logger.warning(
                "Failed to push actions",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Device Management Endpoints
    # ========================================================================
    
    def remove_device(
        self,
        device_auth_token: str,
        parent_user_id: str,
        parent_password_second_hash: str,
        device_id: str
    ) -> APIResponse:
        """Remove a device from the family on the server.
        
        Args:
            device_auth_token: Device auth token for authentication.
            parent_user_id: ID of the parent user making the request.
            parent_password_second_hash: Parent's second password hash or U2F integrity.
            device_id: ID of the device to remove.
            
        Returns:
            APIResponse with ok: true on success.
        """
        request_id = get_request_id()
        
        # Build complete request payload for audit logging (exact fidelity)
        data = {
            'deviceAuthToken': device_auth_token,
            'parentUserId': parent_user_id,
            'parentPasswordSecondHash': parent_password_second_hash,
            'deviceId': device_id
        }
        
        # Get request headers for audit logging (full headers, not sanitized)
        headers = self._get_headers(token=device_auth_token)
        
        # Log the device removal request with complete fidelity to audit log
        audit_log_device_removal_request(
            device_id=device_id,
            parent_user_id=parent_user_id,
            device_auth_token=device_auth_token,
            parent_password_second_hash=parent_password_second_hash,
            request_payload=data,
            request_headers=headers,
            request_id=request_id,
            server_url=self.base_url
        )
        
        # Sanitize request data for regular logging
        sanitized_data = sanitize_dict(data)
        
        logger.info(
            "Removing device from family",
            request_id=request_id,
            device_id=device_id,
            parent_user_id=parent_user_id,
            device_auth_token_preview=device_auth_token[:8] + '...' if device_auth_token else None,
            parent_password_second_hash_preview=parent_password_second_hash[:20] + '...' if parent_password_second_hash else None
        )
        
        response = self._request_with_retry(
            'POST',
            '/parent/remove-device',
            data
        )
        
        # Log the device removal response with complete fidelity to audit log
        audit_log_device_removal_response(
            device_id=device_id,
            parent_user_id=parent_user_id,
            request_id=request_id,
            success=response.success,
            status_code=response.status_code,
            response_data=response.data,
            error_code=response.error_code,
            error_message=response.error_message
        )
        
        if response.success:
            logger.info(
                "Device removed successfully",
                request_id=request_id,
                device_id=device_id
            )
        else:
            logger.warning(
                "Failed to remove device",
                request_id=request_id,
                device_id=device_id,
                error_code=response.error_code,
                error_message=response.error_message,
                status_code=response.status_code,
                response_data_preview=str(response.data)[:200] if response.data else None
            )
        
        return response
    
    def push_device_removal_action(
        self,
        device_auth_token: str,
        parent_user_id: str,
        parent_password_second_hash: str,
        device_id: str,
        sequence_number: int
    ) -> APIResponse:
        """Push a device removal action through the sync protocol.
        
        This method sends a REMOVE_DEVICE action via the sync protocol,
        which is the correct way to remove devices according to the server's
        expected behavior.
        
        Args:
            device_auth_token: Device auth token for authentication.
            parent_user_id: ID of the parent user making the request.
            parent_password_second_hash: Parent's second password hash for integrity.
            device_id: ID of the device to remove.
            sequence_number: The sequence number for this action.
            
        Returns:
            APIResponse with shouldDoFullSync flag on success.
        """
        import json
        from crypto_utils import calculate_hmac_sha256_binary
        
        request_id = get_request_id()
        
        # Build the encoded action (no spaces after colons to match server schema)
        encoded_action = json.dumps({
            "type": "REMOVE_DEVICE",
            "deviceId": device_id
        }, separators=(',', ':'))
        
        # Calculate the integrity hash
        integrity = calculate_hmac_sha256_binary(
            parent_password_second_hash,
            sequence_number,
            device_id,
            encoded_action
        )
        
        # Build the action
        action = {
            "encodedAction": encoded_action,
            "sequenceNumber": sequence_number,
            "integrity": integrity,
            "type": "appLogic",
            "userId": parent_user_id
        }
        
        # Sanitize for logging (remove sensitive fields)
        sanitized_action = {
            'type': action.get('type'),
            'userId': action.get('userId'),
            'sequenceNumber': action.get('sequenceNumber')
        }
        
        logger.info(
            "Pushing device removal action",
            request_id=request_id,
            device_id=device_id,
            parent_user_id=parent_user_id,
            sequence_number=sequence_number,
            action_preview=sanitized_action
        )
        
        # Push the action via sync protocol
        response = self.push_actions(device_auth_token, [action])
        
        if response.success:
            logger.info(
                "Device removal action pushed successfully",
                request_id=request_id,
                device_id=device_id,
                sequence_number=sequence_number
            )
        else:
            logger.warning(
                "Failed to push device removal action",
                request_id=request_id,
                device_id=device_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def check_server_connection(self) -> APIResponse:
        """Check if the server is reachable.
        
        Returns:
            APIResponse indicating server status.
        """
        request_id = get_request_id()
        
        logger.info(
            "Checking server connection",
            request_id=request_id,
            base_url=self.base_url
        )
        
        response = self.get_server_time()
        
        if response.success:
            logger.info(
                "Server connection check successful",
                request_id=request_id
            )
        else:
            logger.warning(
                "Server connection check failed",
                request_id=request_id,
                error_code=response.error_code,
                error_message=response.error_message
            )
        
        return response
    
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()


# ============================================================================
# Convenience Functions
# ============================================================================

def create_auth_client(
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None,
    verbose: bool = False
) -> AuthClient:
    """Create an AuthClient instance.
    
    Args:
        base_url: Base URL for the debug-server.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retries.
        retry_delay: Delay between retries in seconds.
        verbose: Enable verbose logging.
        
    Returns:
        AuthClient instance.
    """
    return AuthClient(
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        verbose=verbose
    )


# Global client instance for convenience
_client: Optional[AuthClient] = None


def get_auth_client() -> AuthClient:
    """Get or create the global AuthClient instance.
    
    Returns:
        AuthClient instance.
    """
    global _client
    if _client is None:
        _client = AuthClient()
    return _client


def reset_auth_client() -> None:
    """Reset the global AuthClient instance (for testing)."""
    global _client
    if _client:
        _client.close()
    _client = None