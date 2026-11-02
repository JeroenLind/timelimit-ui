"""Test to reproduce the missing sign-in links issue.

This test verifies that when a user is not authenticated,
the login links are properly displayed in the dashboard.
"""

import pytest
import json
import os


class TestMissingSignInLinks:
    """Tests for the missing sign-in links issue."""

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_function_exists(self, client):
        """Test that updateSessionOverview function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function updateSessionOverview(data)' in js_content, \
            "updateSessionOverview function not found in JavaScript"
        print("[LOG] updateSessionOverview function exists in JavaScript")

    @pytest.mark.timeout(10)
    def test_updateLoginStatusBanner_function_exists(self, client):
        """Test that updateLoginStatusBanner function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function updateLoginStatusBanner(data)' in js_content, \
            "updateLoginStatusBanner function not found in JavaScript"
        print("[LOG] updateLoginStatusBanner function exists in JavaScript")

    @pytest.mark.timeout(10)
    def test_session_actions_elements_exist_in_html(self, client):
        """Test that the session action links exist in the HTML template."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check that the login action links exist
        assert 'id="create-family-link"' in html_content, \
            "create-family-link element not found in HTML"
        assert 'id="login-existing-family-link"' in html_content, \
            "login-existing-family-link element not found in HTML"
        assert 'id="recover-password-link"' in html_content, \
            "recover-password-link element not found in HTML"
        assert 'id="signout-link"' in html_content, \
            "signout-link element not found in HTML"
        print("[LOG] All session action link elements exist in HTML")

    @pytest.mark.timeout(10)
    def test_session_actions_display_none_by_default(self, client):
        """Test that session action links have proper initial display state."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Find the session-actions section
        assert 'id="session-actions"' in html_content, \
            "session-actions section not found in HTML"

        # Check that create-family-link and login-existing-family-link are visible by default
        # (they should be visible when not authenticated)
        create_family_section = html_content.split('id="create-family-link"')[1].split('</div>')[0]
        login_family_section = html_content.split('id="login-existing-family-link"')[1].split('</div>')[0]

        # These should NOT have display: none by default
        assert 'display: none' not in create_family_section or 'style="display: none"' not in create_family_section, \
            "create-family-link should be visible by default (not display: none)"
        assert 'display: none' not in login_family_section or 'style="display: none"' not in login_family_section, \
            "login-existing-family-link should be visible by default (not display: none)"
        print("[LOG] Session action links have correct initial display state")

    @pytest.mark.timeout(10)
    def test_sign_in_section_element_not_found(self, client):
        """Test that sign-in-section element does NOT exist in HTML and JavaScript doesn't reference it."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # The sign-in-section element should NOT exist in HTML
        has_sign_in_section = 'id="sign-in-section"' in html_content
        assert not has_sign_in_section, \
            "sign-in-section element should not exist in HTML"
        print("[LOG] sign-in-section element does NOT exist in HTML - correct")
        
        # The JavaScript should NOT reference sign-in-section (it was removed as a fix)
        has_sign_in_section_js = 'sign-in-section' in js_content
        assert not has_sign_in_section_js, \
            "JavaScript should not reference sign-in-section (element doesn't exist)"
        print("[LOG] JavaScript does not reference sign-in-section - fix verified")

    @pytest.mark.timeout(10)
    def test_domcontentloaded_calls_update_functions(self, client):
        """Test that DOMContentLoaded handler calls updateSessionOverview and updateLoginStatusBanner."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Find the DOMContentLoaded handler
        assert "document.addEventListener('DOMContentLoaded'" in js_content, \
            "DOMContentLoaded event listener not found"

        # Check that updateSessionOverview is called after checkAuthentication
        # The calls should be in the DOMContentLoaded handler
        # Use a more robust method to find the handler - look for the closing of the IIFE
        domcontentloaded_section = js_content.split("document.addEventListener('DOMContentLoaded'")[1].split('})()')[0]

        assert 'updateLoginStatusBanner(sessionData)' in domcontentloaded_section, \
            "updateLoginStatusBanner(sessionData) not called in DOMContentLoaded handler"
        assert 'updateSessionOverview(sessionData)' in domcontentloaded_section, \
            "updateSessionOverview(sessionData) not called in DOMContentLoaded handler"
        print("[LOG] DOMContentLoaded handler correctly calls update functions")

    @pytest.mark.timeout(10)
    def test_session_status_returns_authenticated_false(self, client):
        """Test that session status returns authenticated: false when not logged in."""
        # Mock the pre-loaded tokens to simulate no persisted session
        import app as app_module
        app_module._preloaded_device_auth_token = None
        app_module._preloaded_own_device_id = None

        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is False, \
            "Session status should show authenticated: false when not logged in"
        assert data['has_device_auth_token'] is False, \
            "Session status should show has_device_auth_token: false when not logged in"
        print("[LOG] Session status correctly returns authenticated: false")