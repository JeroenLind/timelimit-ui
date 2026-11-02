"""Test for sidebar sign out button event listener.

This test verifies that the sidebar sign out button has a proper event listener
attached to it, so clicking it actually triggers the sign out functionality.
"""

import pytest
import os


class TestSidebarSignOutButton:
    """Tests for the sidebar sign out button event listener."""

    @pytest.mark.timeout(10)
    def test_sidebar_sign_out_button_exists_in_html(self, client):
        """Test that the sidebar sign out button element exists in the HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for the sidebar sign out button element
        assert 'id="signout-btn-sidebar"' in html_content, \
            "Sidebar sign out button with id='signout-btn-sidebar' not found in HTML"
        print("[LOG] Sidebar sign out button element exists in HTML")

    @pytest.mark.timeout(10)
    def test_main_sign_out_button_has_onclick_handler(self, client):
        """Test that the main sign out button has an onclick handler."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for the main sign out button with onclick
        assert 'id="signout-btn"' in html_content, \
            "Main sign out button with id='signout-btn' not found in HTML"
        assert 'onclick="clearSession()"' in html_content, \
            "Main sign out button missing onclick='clearSession()' handler"
        print("[LOG] Main sign out button has onclick handler")

    @pytest.mark.timeout(10)
    def test_sidebar_sign_out_button_has_click_event_listener(self, client):
        """Test that the sidebar sign out button has a click event listener that calls clearSession."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # The sidebar sign out button should have an event listener that calls clearSession
        # Look for the pattern: getElementById('signout-btn-sidebar').addEventListener('click', ...clearSession...)
        # or similar pattern that attaches clearSession to the sidebar button

        # First, check that clearSession is exposed globally
        assert 'window.clearSession = clearSession' in js_content, \
            "clearSession not exposed on window object"

        # Check that there's an event listener for signout-btn-sidebar that calls clearSession
        # The pattern should be something like:
        # const signoutBtnSidebar = document.getElementById('signout-btn-sidebar');
        # if (signoutBtnSidebar) { signoutBtnSidebar.addEventListener('click', clearSession); }
        # or:
        # document.getElementById('signout-btn-sidebar').addEventListener('click', clearSession);

        # Look for the specific pattern where signout-btn-sidebar gets an event listener
        has_sidebar_listener = False

        # Check for the pattern in the DOMContentLoaded handler
        # Look for signout-btn-sidebar being used with addEventListener
        lines = js_content.split('\n')
        for i, line in enumerate(lines):
            if 'signout-btn-sidebar' in line and 'addEventListener' in line:
                has_sidebar_listener = True
                break
            # Also check if the next few lines after getting the element contain addEventListener
            if 'signoutBtnSidebar' in line and 'getElementById' in line:
                # Check surrounding lines for addEventListener
                context = '\n'.join(lines[max(0, i-2):min(len(lines), i+10)])
                if 'addEventListener' in context and 'clearSession' in context:
                    has_sidebar_listener = True
                    break

        assert has_sidebar_listener, \
            "Sidebar sign out button (signout-btn-sidebar) missing click event listener that calls clearSession"
        print("[LOG] Sidebar sign out button has click event listener that calls clearSession")

    @pytest.mark.timeout(10)
    def test_clearSession_function_exists_and_exposed(self, client):
        """Test that clearSession function exists and is exposed globally."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check that clearSession function is defined
        assert 'function clearSession()' in js_content, \
            "clearSession function not found in JavaScript"

        # Check that it's exposed globally
        assert 'window.clearSession = clearSession' in js_content, \
            "clearSession not exposed on window object"
        print("[LOG] clearSession function exists and is exposed globally")

    @pytest.mark.timeout(10)
    def test_sidebar_sign_out_button_click_calls_clearSession(self, client):
        """Test that clicking the sidebar sign out button calls clearSession function."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check that there's a pattern where signout-btn-sidebar's click event calls clearSession
        # This should be in the DOMContentLoaded handler

        # Look for the pattern: clearSession() being called in a click handler for signout-btn-sidebar
        # The code should look something like:
        # if (signoutBtnSidebar) {
        #     signoutBtnSidebar.addEventListener('click', function() {
        #         clearSession();
        #     });
        # }

        # Check that clearSession is called somewhere in the file
        assert 'clearSession()' in js_content, \
            "clearSession() function call not found in JavaScript"

        # Check that there's a click handler for signout-btn-sidebar
        # Look for the pattern where signoutBtnSidebar is used with addEventListener
        has_click_handler = False

        # Check for the pattern in the DOMContentLoaded handler
        lines = js_content.split('\n')
        for i, line in enumerate(lines):
            if 'signoutBtnSidebar' in line:
                # Check surrounding lines for addEventListener and clearSession
                context = '\n'.join(lines[max(0, i-5):min(len(lines), i+15)])
                if 'addEventListener' in context and 'clearSession' in context:
                    has_click_handler = True
                    break

        assert has_click_handler, \
            "No click event handler found for signout-btn-sidebar that calls clearSession"
        print("[LOG] Sidebar sign out button click handler calls clearSession")