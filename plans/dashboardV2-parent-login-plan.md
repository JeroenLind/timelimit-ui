# DashboardV2: Parent Login to Existing Family - Implementation Plan

## Overview

This plan outlines the steps to add functionality to dashboardV2 that allows a parent to log in to an existing family using email-based authentication. This is different from "Create Family" which creates a new family - this allows joining an existing family.

## Key Finding from Analysis

The `sign-in-into-family` endpoint does **NOT** require a password! It only requires:
- `mailAuthToken` (from email verification)
- `deviceName`
- `parentDevice.model`
- `clientLevel` (optional, defaults to 7)

This matches the Android app's `signInToFamilyByMailToken` implementation.

## Implementation Flow

```
Step 1: Enter Email → Send Mail Login Code
    ↓
Step 2: Enter Verification Code → Get MailAuthToken
    ↓
Step 3: Enter Device Info → Sign In to Family
    ↓
Success: Redirect to Dashboard with deviceAuthToken
```

## Step-by-Step Implementation Plan

### Step 1: Add New Route for Parent Login Page

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add a new route `/login-as-parent` that renders a page for logging into an existing family.

```python
@app.route('/login-as-parent', methods=['GET'])
def get_login_as_parent():
    """Render the parent login page for existing family."""
    # Check if already authenticated
    if session.get('device_auth_token'):
        return redirect('/dashboardV2')
    
    # Clear any previous login state
    session.pop('mail_login_token', None)
    session.pop('mail_auth_token', None)
    
    return render_template('login_as_parent.html')
```

### Step 2: Create Login As Parent Template

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html`

Create a new HTML template with a 3-step form:
- Step 1: Enter email address
- Step 2: Enter verification code
- Step 3: Enter device information

The template should follow the same styling as `create_family.html` for consistency.

```html
{% extends "base.html" %}

{% block title %}Login to Existing Family - TimeLimit Dashboard{% endblock %}

{% block extra_css %}
<style>
    .login-family-container {
        max-width: 480px;
        margin: 0 auto;
    }
    
    .form-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .step-indicator {
        display: flex;
        justify-content: center;
        margin-bottom: 24px;
    }
    
    .step-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.2);
        margin: 0 8px;
    }
    
    .step-dot.active {
        background: #fff;
    }
    
    .form-group {
        margin-bottom: 20px;
    }
    
    .form-group label {
        display: block;
        color: #aaa;
        font-size: 14px;
        margin-bottom: 8px;
    }
    
    .form-group input {
        width: 100%;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background: rgba(255, 255, 255, 0.05);
        color: #fff;
        font-size: 16px;
    }
    
    .form-group input:focus {
        outline: none;
        border-color: rgba(255, 255, 255, 0.3);
    }
    
    .form-group input::placeholder {
        color: rgba(255, 255, 255, 0.3);
    }
    
    .password-hint {
        color: rgba(255, 255, 255, 0.4);
        font-size: 12px;
        margin-top: 4px;
    }
    
    .error-message {
        background: rgba(244, 67, 54, 0.2);
        border: 1px solid rgba(244, 67, 54, 0.5);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 20px;
        color: #ff8a80;
    }
    
    .btn {
        width: 100%;
        padding: 12px 24px;
        border-radius: 8px;
        border: none;
        background: #3f51b5;
        color: #fff;
        font-size: 16px;
        cursor: pointer;
        transition: background 0.2s;
    }
    
    .btn:hover {
        background: #5368ce;
    }
    
    .back-link {
        display: block;
        text-align: center;
        margin-top: 20px;
        color: rgba(255, 255, 255, 0.5);
        font-size: 14px;
    }
    
    .back-link:hover {
        color: rgba(255, 255, 255, 0.8);
    }
</style>
{% endblock %}

{% block content %}
<div class="login-family-container">
    <div class="form-card">
        <h2>Login to Existing Family</h2>
        
        {% if error %}
        <div class="error-message">
            {{ error }}
        </div>
        {% endif %}
        
        {% if step == 1 %}
        <!-- Step 1: Enter Email -->
        <form method="POST" action="/login-as-parent">
            <input type="hidden" name="step" value="1">
            
            <div class="step-indicator">
                <div class="step-dot active"></div>
                <div class="step-dot"></div>
                <div class="step-dot"></div>
            </div>
            
            <div class="form-group">
                <label for="mail">Email Address</label>
                <input type="email" id="mail" name="mail" placeholder="you@example.com" required autofocus>
            </div>
            
            <button type="submit" class="btn">Send Verification Code</button>
        </form>
        
        {% elif step == 2 %}
        <!-- Step 2: Enter Verification Code -->
        <form method="POST" action="/login-as-parent">
            <input type="hidden" name="step" value="2">
            
            <div class="step-indicator">
                <div class="step-dot"></div>
                <div class="step-dot active"></div>
                <div class="step-dot"></div>
            </div>
            
            <div class="form-group">
                <label for="receivedCode">Verification Code</label>
                <input type="text" id="receivedCode" name="receivedCode" placeholder="e.g., Pferd Miete abwenden" required autofocus>
                <div class="password-hint">Enter the 3-word code sent to your email</div>
            </div>
            
            <button type="submit" class="btn">Continue</button>
        </form>
        
        {% elif step == 3 %}
        <!-- Step 3: Enter Device Info -->
        <form method="POST" action="/login-as-parent">
            <input type="hidden" name="step" value="3">
            
            <div class="step-indicator">
                <div class="step-dot"></div>
                <div class="step-dot"></div>
                <div class="step-dot active"></div>
            </div>
            
            <div class="form-group">
                <label for="deviceModel">Device Model</label>
                <input type="text" id="deviceModel" name="deviceModel" placeholder="e.g., Pixel 7" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="deviceName">Device Name</label>
                <input type="text" id="deviceName" name="deviceName" placeholder="e.g., Parent's Phone" required>
            </div>
            
            <button type="submit" class="btn">Login to Family</button>
        </form>
        {% endif %}
        
        <form method="POST" action="/login-as-parent/cancel" style="margin-top: 20px;">
            <button type="submit" class="btn" style="background: rgba(244, 67, 54, 0.3); border: 1px solid rgba(244, 67, 54, 0.5);">
                Cancel
            </button>
        </form>
        
        <a href="/dashboardV2" class="back-link">← Back to Dashboard</a>
    </div>
</div>
{% endblock %}

<!-- No JavaScript needed - using HTML5 autofocus attribute -->
```

### Step 3: Add POST Handler for Login As Parent

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add a POST route to handle the login flow:

```python
@app.route('/login-as-parent', methods=['POST'])
def post_login_as_parent():
    """Process parent login form submission."""
    # Handle all three steps:
    # - Step 1: Send mail login code
    # - Step 2: Sign in by mail code
    # - Step 3: Sign in to family
```

### Step 4: Add Cancel Route

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add a cancel route to clear session data:

```python
@app.route('/login-as-parent/cancel', methods=['POST'])
def cancel_login_as_parent():
    """Cancel login as parent flow and clear session."""
    request_id = get_request_id()
    
    # Clear all login session data
    session.pop('mail_login_token', None)
    session.pop('mail_auth_token', None)
    session.pop('device_auth_token', None)
    session.pop('own_device_id', None)
    session.pop('login_as_parent_error', None)
    
    logger.info("Login as parent cancelled", request_id=request_id)
    return redirect('/dashboardV2')
```

### Step 5: Update DashboardV2 Template

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`

Add a "Login to Existing Family" link in the session information section, similar to the "Create New Family" link.

### Step 6: Update AuthClient.sign_in_into_family Method

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`

The existing method (lines 654-713) has bugs that need to be fixed:

1. **Bug 1:** Sends `deviceModel` as a flat field, but server expects `parentDevice: {model: "..."}`
2. **Bug 2:** Requires `parent_password_second_hash` as a required parameter, but it's NOT required for email-based sign-in
3. **Bug 3:** Does not send `clientLevel`

**Fix needed in auth_client.py:**

```python
data = {
    'mailAuthToken': mail_auth_token,
    'parentDevice': {'model': device_model} if device_model else {'model': 'Unknown'},
    'deviceName': device_name
}
if client_level:
    data['clientLevel'] = client_level
```

### Step 7: Update AuthClient.sign_in_into_family Method (Fix)

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`

Update the `sign_in_into_family` method (lines 654-713) to correctly format the request:

```python
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
```

### Step 8: Update app.py POST Handler to Use Correct Parameters

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Update the call to `client.sign_in_into_family()` in the POST handler:

```python
response = client.sign_in_into_family(
    mail_auth_token=mail_auth_token,
    device_name=device_name,
    device_model=device_model,
    client_level=7  # Matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
)
```

### Step 9: Add Tests

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py`

Create unit tests for the new functionality:

```python
"""Tests for login as parent functionality."""

import pytest
from app import app, db
from auth_client import AuthClient


@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            db.init_db()
        yield client


def test_get_login_as_parent_step1(client):
    """Test GET /login-as-parent renders step 1."""
    response = client.get('/login-as-parent')
    assert response.status_code == 200
    assert b'Login to Existing Family' in response.data


def test_post_login_as_parent_step1_missing_email(client):
    """Test POST /login-as-parent step 1 with missing email."""
    response = client.post('/login-as-parent', data={
        'step': '1'
    }, follow_redirects=True)
    assert b'Email is required' in response.data


def test_post_login_as_parent_step1_invalid_email(client):
    """Test POST /login-as-parent step 1 with invalid email."""
    response = client.post('/login-as-parent', data={
        'step': '1',
        'mail': 'invalid-email'
    }, follow_redirects=True)
    assert b'Invalid email format' in response.data


def test_sign_in_into_family_request_format():
    """Test that sign_in_into_family sends correct request format."""
    client = AuthClient(base_url='http://test-server')
    
    # Mock the _request_with_retry method to capture the request
    captured_data = {}
    
    def mock_request(method, endpoint, data=None, token=None, retry_count=0, skip_prefix=False):
        captured_data.update(data or {})
        from auth_client import APIResponse
        return APIResponse(
            success=True,
            status_code=200,
            data={'deviceAuthToken': 'test-token', 'ownDeviceId': 'test-device-id'}
        )
    
    client._request_with_retry = mock_request
    
    # Call the method
    response = client.sign_in_into_family(
        mail_auth_token='test-mail-token',
        device_name='Test Device',
        device_model='Test Model'
    )
    
    # Verify the request format
    assert captured_data['mailAuthToken'] == 'test-mail-token'
    assert captured_data['deviceName'] == 'Test Device'
    assert captured_data['parentDevice'] == {'model': 'Test Model'}
    assert response.success
```

### Step 10: Update Route Registration

**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Update the routes logged in the main block (around line 1701):

```python
routes=[
    '/', '/legacy-dashboard', '/dashboard.html', '/dashboardV2',
    '/select-server', '/api/server-selection', '/api/time',
    '/api/auth/send-mail-login-code', '/api/auth/sign-in-by-mail-code',
    '/api/auth/create-family', '/api/families', '/api/auth/sign-in-into-family',
    '/api/parent/create-add-device-token', '/api/child/add-device',
    '/api/auth/get-status-by-mail-address', '/api/auth/recover-parent-password',
    '/api/session/clear', '/api/session/status',
    '/api/timechecker/status', '/api/timechecker/history',
    '/health',
    '/create-family', '/create-family/cancel',
    '/login-as-parent', '/login-as-parent/cancel'
]
```

## Testing Checklist

- [ ] Step 1: Email validation works correctly
- [ ] Step 2: Verification code validation works correctly
- [ ] Step 3: Device info validation works correctly
- [ ] Session management works correctly
- [ ] Error handling works correctly
- [ ] Redirect to dashboard on success
- [ ] Cancel button clears session and redirects to dashboard
- [ ] Already authenticated users are redirected to dashboard
- [ ] Request format matches server schema

## Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Add routes and handlers
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Fix sign_in_into_family method
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html` - Create new template
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Add link to login page
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py` - Create tests
6. `c:/git/timelimit-ui/CONTEXT.md` - Document changes

## Notes

- The sign-in-into-family endpoint does NOT require a password, only email verification
- The parentDevice field must be an object with a model field, not a flat deviceModel field
- The clientLevel should be set to 7 to match the Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
- The flow is similar to create-family but skips the password step

## JavaScript Minimization

The implementation uses **no JavaScript** for the login flow:

1. **Form validation** is handled server-side in Python (see `post_login_as_parent()` in app.py)
2. **Input focus** uses HTML5 `autofocus` attribute instead of JavaScript
3. **Form submission** uses standard HTML form POST requests, not AJAX

This follows the project's preference for Python-based implementation over JavaScript.