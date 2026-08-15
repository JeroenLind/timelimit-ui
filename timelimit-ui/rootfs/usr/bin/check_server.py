"""Server connection checking utility for TimeLimit UI.

This module provides robust server connection checking with:
- Configurable connection timeouts
- Retry mechanisms with exponential backoff
- Structured error responses for frontend interpretation
- Detailed server-side logging for troubleshooting

Usage:
    from check_server import ServerChecker, ServerCheckResult
    
    checker = ServerChecker("http://192.168.68.30:8080", timeout=5, max_retries=3)
    result = checker.check()
    
    if result.success:
        print(f"Server time: {result.server_time}")
    else:
        print(f"Error: {result.error_code} - {result.user_message}")
"""

import json
import time
import socket
import urllib.request
import urllib.error
import ssl
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Configure module logger
logger = logging.getLogger('timelimit-ui.check_server')

# ============================================================================
# Error Codes - Used for structured error responses
# ============================================================================

ERROR_CODE_TIMEOUT = "timeout"
ERROR_CODE_UNREACHABLE = "unreachable"
ERROR_CODE_INVALID_RESPONSE = "invalid_response"
ERROR_CODE_SERVER_ERROR = "server_error"
ERROR_CODE_UNKNOWN = "unknown"

# User-friendly messages for each error code (shown in UI)
USER_MESSAGES: Dict[str, str] = {
    ERROR_CODE_TIMEOUT: "Server did not respond within the timeout period. Please check your network connection and try again.",
    ERROR_CODE_UNREACHABLE: "Cannot reach the TimeLimit server. Please verify the server URL and ensure the server is running.",
    ERROR_CODE_INVALID_RESPONSE: "Server returned an unexpected response. This may indicate a version mismatch or server issue.",
    ERROR_CODE_SERVER_ERROR: "The TimeLimit server returned an error. Please try again later.",
    ERROR_CODE_UNKNOWN: "An unexpected error occurred while checking the server. Please try again.",
}


@dataclass
class ServerCheckResult:
    """Result of a server connection check.
    
    Attributes:
        success: Whether the server check was successful
        error_code: Error code if failed (timeout, unreachable, invalid_response, server_error, unknown)
        user_message: User-friendly message for display in the UI
        technical_detail: Technical details for debugging (logged server-side)
        server_time: Server time in milliseconds if successful
        attempts: Number of attempts made (including retries)
        server_url: The server URL that was checked
    """
    success: bool
    error_code: Optional[str] = None
    user_message: Optional[str] = None
    technical_detail: Optional[str] = None
    server_time: Optional[int] = None
    attempts: int = 0
    server_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "attempts": self.attempts,
            "server_url": self.server_url,
        }
        if self.success:
            result["time"] = self.server_time
        else:
            result["status"] = "error"
            result["error_code"] = self.error_code
            result["user_message"] = self.user_message
            result["technical_detail"] = self.technical_detail
        return result


class ServerChecker:
    """Checks server connectivity with retry and timeout support.
    
    This class provides robust server connection checking with:
    - Configurable connection timeouts
    - Retry mechanisms with exponential backoff
    - Structured error responses
    - Detailed logging
    
    Example:
        checker = ServerChecker(
            server_url="http://192.168.68.30:8080",
            timeout=5,
            max_retries=3,
            retry_delay=1.0
        )
        result = checker.check()
    """
    
    def __init__(
        self,
        server_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        verbose: bool = False
    ):
        """Initialize the server checker.
        
        Args:
            server_url: The base URL of the TimeLimit server (e.g., "http://192.168.68.30:8080")
            timeout: Connection timeout in seconds (default: 10.0)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 1.0)
            verbose: Enable verbose logging (default: False)
        """
        self.server_url = server_url.strip().rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.verbose = verbose
        self.ssl_context = ssl._create_unverified_context()
        
        # Set up logging level based on verbose flag
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def _log(self, level: int, message: str) -> None:
        """Log a message respecting the verbose setting.
        
        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO, logging.ERROR)
            message: The message to log
        """
        if level == logging.DEBUG and not self.verbose:
            return
        logger.log(level, message)
    
    def _make_request(self) -> tuple:
        """Make a single HTTP request to the /time endpoint.
        
        Uses GET method as per the official TimeLimit API specification.
        
        Returns:
            Tuple of (status_code, response_body) or raises an exception
            
        Raises:
            socket.timeout: If the connection times out
            ConnectionRefusedError: If the server is unreachable
            urllib.error.URLError: For other URL errors
            urllib.error.HTTPError: For HTTP error responses
        """
        target_url = f"{self.server_url}/time"
        
        self._log(logging.DEBUG, f"Making request to: {target_url}")
        
        req = urllib.request.Request(
            target_url,
            headers={'Content-Type': 'application/json'},
            method='GET'
        )
        
        with urllib.request.urlopen(req, context=self.ssl_context, timeout=self.timeout) as response:
            status_code = response.status
            body = response.read()
            self._log(logging.DEBUG, f"Response status: {status_code}, body size: {len(body)} bytes")
            return status_code, body
    
    def _parse_response(self, status_code: int, body: bytes) -> tuple:
        """Parse the server response.
        
        Args:
            status_code: HTTP status code
            body: Response body as bytes
            
        Returns:
            Tuple of (success, server_time or error_info)
        """
        if status_code != 200:
            return False, {
                "error_code": ERROR_CODE_SERVER_ERROR,
                "technical_detail": f"Server returned HTTP {status_code}"
            }
        
        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            return False, {
                "error_code": ERROR_CODE_INVALID_RESPONSE,
                "technical_detail": f"Invalid JSON response: {str(e)}"
            }
        
        if 'time' not in data:
            return False, {
                "error_code": ERROR_CODE_INVALID_RESPONSE,
                "technical_detail": "Response missing 'time' field"
            }
        
        server_time = data['time']
        if not isinstance(server_time, (int, float)):
            return False, {
                "error_code": ERROR_CODE_INVALID_RESPONSE,
                "technical_detail": f"'time' field is not a number: {type(server_time).__name__}"
            }
        
        return True, {"server_time": int(server_time)}
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate the delay before the next retry using exponential backoff.
        
        Args:
            attempt: The current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        return self.retry_delay * (2 ** attempt)
    
    def check(self) -> ServerCheckResult:
        """Check server connectivity by requesting the /time endpoint.
        
        This method implements retry logic with exponential backoff for
        transient failures. It handles various error conditions and returns
        a structured result that can be serialized to JSON.
        
        Returns:
            ServerCheckResult with success status, error info (if failed),
            server time (if successful), and attempt count.
        """
        self._log(logging.INFO, f"Starting server check for: {self.server_url}")
        
        last_error: Optional[Dict[str, str]] = None
        actual_attempts = 0
        
        for attempt in range(self.max_retries):
            actual_attempts = attempt + 1
            self._log(logging.DEBUG, f"Attempt {actual_attempts}/{self.max_retries}")
            
            try:
                status_code, body = self._make_request()
                success, result = self._parse_response(status_code, body)
                
                if success:
                    self._log(logging.INFO, f"Server check successful after {actual_attempts} attempt(s)")
                    return ServerCheckResult(
                        success=True,
                        server_time=result["server_time"],
                        attempts=actual_attempts,
                        server_url=self.server_url
                    )
                else:
                    last_error = result
                    self._log(logging.WARNING, f"Invalid response on attempt {actual_attempts}: {result}")
                    
            except socket.timeout as e:
                last_error = {
                    "error_code": ERROR_CODE_TIMEOUT,
                    "technical_detail": f"Connection timeout after {self.timeout}s: {str(e)}"
                }
                self._log(logging.WARNING, f"Timeout on attempt {actual_attempts}: {str(e)}")
                
            except urllib.error.HTTPError as e:
                # HTTPError must be caught before URLError (HTTPError is a subclass of URLError)
                last_error = {
                    "error_code": ERROR_CODE_SERVER_ERROR,
                    "technical_detail": f"HTTP error {e.code}: {e.reason}"
                }
                self._log(logging.WARNING, f"HTTP error on attempt {actual_attempts}: {e.code} {e.reason}")
                
            except ConnectionRefusedError as e:
                last_error = {
                    "error_code": ERROR_CODE_UNREACHABLE,
                    "technical_detail": f"Connection refused: {str(e)}"
                }
                self._log(logging.ERROR, f"Connection refused on attempt {actual_attempts}: {str(e)}")
                # Don't retry on connection refused - server is definitely not running
                break
                
            except urllib.error.URLError as e:
                # URLError covers various connection issues (ECONNREFUSED, EHOSTUNREACH, etc.)
                error_reason = str(e.reason) if hasattr(e, 'reason') else str(e)
                last_error = {
                    "error_code": ERROR_CODE_UNREACHABLE,
                    "technical_detail": f"URL error: {error_reason}"
                }
                self._log(logging.ERROR, f"URL error on attempt {actual_attempts}: {error_reason}")
                # Don't retry on connection refused errors
                if "Connection refused" in error_reason or "ECONNREFUSED" in error_reason:
                    break
                
            except Exception as e:
                last_error = {
                    "error_code": ERROR_CODE_UNKNOWN,
                    "technical_detail": f"Unexpected error: {type(e).__name__}: {str(e)}"
                }
                self._log(logging.ERROR, f"Unexpected error on attempt {actual_attempts}: {type(e).__name__}: {str(e)}")
            
            # If not the last attempt, wait before retrying
            if attempt < self.max_retries - 1:
                delay = self._calculate_retry_delay(attempt)
                self._log(logging.DEBUG, f"Waiting {delay}s before retry...")
                time.sleep(delay)
        
        # All attempts failed
        if last_error is None:
            last_error = {
                "error_code": ERROR_CODE_UNKNOWN,
                "technical_detail": "Unknown error - no error details captured"
            }
        
        self._log(logging.ERROR, f"Server check failed after {actual_attempts} attempt(s): {last_error['error_code']}")
        
        return ServerCheckResult(
            success=False,
            error_code=last_error["error_code"],
            user_message=USER_MESSAGES.get(last_error["error_code"], USER_MESSAGES[ERROR_CODE_UNKNOWN]),
            technical_detail=last_error["technical_detail"],
            attempts=actual_attempts,
            server_url=self.server_url
        )


def check_server_connection(
    server_url: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    verbose: bool = False
) -> ServerCheckResult:
    """Convenience function to check server connectivity.
    
    Args:
        server_url: The base URL of the TimeLimit server
        timeout: Connection timeout in seconds
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        verbose: Enable verbose logging
        
    Returns:
        ServerCheckResult with check outcome
    """
    checker = ServerChecker(
        server_url=server_url,
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        verbose=verbose
    )
    return checker.check()


# ============================================================================
# Utility functions for error handling
# ============================================================================

def get_user_message(error_code: str) -> str:
    """Get the user-friendly message for an error code.
    
    Args:
        error_code: The error code (timeout, unreachable, invalid_response, server_error, unknown)
        
    Returns:
        User-friendly message string
    """
    return USER_MESSAGES.get(error_code, USER_MESSAGES[ERROR_CODE_UNKNOWN])


def is_error_code(error_code: str) -> bool:
    """Check if a string is a valid error code.
    
    Args:
        error_code: The string to check
        
    Returns:
        True if it's a valid error code, False otherwise
    """
    return error_code in USER_MESSAGES


if __name__ == "__main__":
    # Example usage when run directly
    import sys
    
    # Set up basic logging for standalone execution
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = "http://localhost:8080"
    
    print(f"Checking server: {server_url}")
    result = check_server_connection(server_url, verbose=True)
    
    if result.success:
        print(f"✅ Success! Server time: {result.server_time}")
        print(f"   Attempts: {result.attempts}")
    else:
        print(f"❌ Failed: {result.error_code}")
        print(f"   User message: {result.user_message}")
        print(f"   Technical detail: {result.technical_detail}")
        print(f"   Attempts: {result.attempts}")