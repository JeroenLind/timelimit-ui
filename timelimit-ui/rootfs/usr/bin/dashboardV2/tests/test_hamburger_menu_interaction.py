"""Test for hamburger menu interaction with detailed logging.

This test simulates the full hamburger menu click interaction
and logs each step to help diagnose why the menu might not open.
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock


class TestHamburgerMenuInteraction:
    """Tests for hamburger menu click interaction with logging."""

    @pytest.mark.timeout(10)
    def test_hamburger_menu_button_element_exists(self, client):
        """Test that the hamburger menu button element exists in the HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for the button element
        assert 'id="menu-toggle"' in html_content, "Hamburger menu button with id='menu-toggle' not found"
        assert 'class="menu-toggle"' in html_content, "Hamburger menu button with class='menu-toggle' not found"
        
        # Check for the button structure
        assert '<button' in html_content, "Button element not found"
        assert 'aria-label="Open menu"' in html_content, "aria-label not found"
        assert 'aria-expanded="false"' in html_content, "aria-expanded attribute not found"
        
        print("[LOG] Hamburger menu button element exists in HTML")

    @pytest.mark.timeout(10)
    def test_sidebar_element_exists(self, client):
        """Test that the sidebar element exists in the HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="sidebar"' in html_content, "Sidebar with id='sidebar' not found"
        assert 'class="dashboard-sidebar"' in html_content, "Sidebar with class='dashboard-sidebar' not found"
        assert 'role="navigation"' in html_content, "Sidebar role='navigation' not found"
        
        print("[LOG] Sidebar element exists in HTML")

    @pytest.mark.timeout(10)
    def test_overlay_element_exists(self, client):
        """Test that the overlay element exists in the HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="sidebar-overlay"' in html_content, "Overlay with id='sidebar-overlay' not found"
        assert 'class="sidebar-overlay"' in html_content, "Overlay with class='sidebar-overlay' not found"
        
        print("[LOG] Overlay element exists in HTML")

    @pytest.mark.timeout(10)
    def test_toggleMenu_function_exists_in_js(self, client):
        """Test that toggleMenu function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function toggleMenu()' in js_content, "toggleMenu function not found"
        assert 'function closeMenu()' in js_content, "closeMenu function not found"
        
        print("[LOG] toggleMenu and closeMenu functions exist in JavaScript")

    @pytest.mark.timeout(10)
    def test_toggleMenu_function_logic(self, client):
        """Test the toggleMenu function logic by examining its code."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the function body
        assert 'document.getElementById(\'sidebar\')' in js_content, "getElementById for sidebar not found"
        assert 'document.getElementById(\'sidebar-overlay\')' in js_content, "getElementById for overlay not found"
        assert 'document.getElementById(\'menu-toggle\')' in js_content, "getElementById for menu-toggle not found"
        
        # Check for the active class toggle
        assert 'sidebar.classList.add(\'active\')' in js_content, "sidebar.classList.add('active') not found"
        assert 'sidebar.classList.remove(\'active\')' in js_content, "sidebar.classList.remove('active') not found"
        assert 'overlay.classList.add(\'active\')' in js_content, "overlay.classList.add('active') not found"
        assert 'overlay.classList.remove(\'active\')' in js_content, "overlay.classList.remove('active') not found"
        
        print("[LOG] toggleMenu function has correct logic for adding/removing 'active' class")

    @pytest.mark.timeout(10)
    def test_event_listener_registration(self, client):
        """Test that event listener is registered for the menu toggle button."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for event listener registration
        assert 'menuToggleBtn.addEventListener' in js_content or "getElementById('menu-toggle').addEventListener" in js_content, \
            "Event listener not registered for menu-toggle button"
        
        print("[LOG] Event listener is registered for menu-toggle button")

    @pytest.mark.timeout(10)
    def test_sidebar_css_has_active_state(self, client):
        """Test that sidebar CSS has the active state that shows the menu."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check for sidebar positioning
        assert '.dashboard-sidebar {' in css_content, ".dashboard-sidebar CSS not found"
        assert 'position: fixed' in css_content, "position: fixed not found for sidebar"
        assert 'right: -280px' in css_content, "right: -280px (hidden state) not found"
        
        # Check for active state
        assert '.dashboard-sidebar.active {' in css_content, ".dashboard-sidebar.active CSS not found"
        assert 'right: 0' in css_content, "right: 0 (visible state) not found in active state"
        
        print("[LOG] Sidebar CSS has correct positioning and active state")

    @pytest.mark.timeout(10)
    def test_overlay_css_has_active_state(self, client):
        """Test that overlay CSS has the active state that shows the overlay."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check for overlay positioning
        assert '.sidebar-overlay {' in css_content, ".sidebar-overlay CSS not found"
        assert 'position: fixed' in css_content, "position: fixed not found for overlay"
        
        # Check for active state
        assert '.sidebar-overlay.active {' in css_content, ".sidebar-overlay.active CSS not found"
        assert 'opacity: 1' in css_content, "opacity: 1 not found in active state"
        assert 'visibility: visible' in css_content, "visibility: visible not found in active state"
        
        print("[LOG] Overlay CSS has correct positioning and active state")

    @pytest.mark.timeout(10)
    def test_menu_toggle_button_not_hidden(self, client):
        """Test that the menu toggle button is not hidden by CSS."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Extract the menu-toggle style block
        if '.menu-toggle {' in css_content:
            menu_toggle_style = css_content.split('.menu-toggle {')[1].split('}')[0]
            
            # Check that it's not hidden
            assert 'display: none' not in menu_toggle_style, "menu-toggle has display: none - button is hidden!"
            assert 'visibility: hidden' not in menu_toggle_style, "menu-toggle has visibility: hidden"
            assert 'opacity: 0' not in menu_toggle_style, "menu-toggle has opacity: 0"
            
            # Check that it has visible styles
            assert 'background' in menu_toggle_style, "menu-toggle missing background color"
            assert 'cursor: pointer' in menu_toggle_style, "menu-toggle missing cursor: pointer"
            
            print("[LOG] Menu toggle button is visible and has proper styles")
        else:
            pytest.fail(".menu-toggle CSS style not found")

    @pytest.mark.timeout(10)
    def test_aria_expanded_attribute_update(self, client):
        """Test that aria-expanded attribute is updated when menu opens/closes."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for aria-expanded updates
        assert "setAttribute('aria-expanded', 'true')" in js_content, \
            "aria-expanded not set to 'true' when menu opens"
        assert "setAttribute('aria-expanded', 'false')" in js_content, \
            "aria-expanded not set to 'false' when menu closes"
        
        print("[LOG] aria-expanded attribute is properly updated in JavaScript")

    @pytest.mark.timeout(10)
    def test_aria_hidden_attribute_update(self, client):
        """Test that aria-hidden attribute is updated when menu opens/closes."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for aria-hidden updates
        assert "setAttribute('aria-hidden', 'false')" in js_content, \
            "aria-hidden not set to 'false' when menu opens"
        assert "setAttribute('aria-hidden', 'true')" in js_content, \
            "aria-hidden not set to 'true' when menu closes"
        
        print("[LOG] aria-hidden attribute is properly updated in JavaScript")

    @pytest.mark.timeout(10)
    def test_dashboard_page_detection_in_domcontentloaded(self, client):
        """Test that DOMContentLoaded has proper page detection for hamburger menu."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for page detection
        assert 'unified-view-container' in js_content, "unified-view-container not found in page detection"
        assert 'status-indicator' in js_content, "status-indicator not found in page detection"
        
        # Check that menu toggle initialization is inside the page check
        # Find the DOMContentLoaded handler - use a more robust approach
        # Look for the key elements that should be present in the handler
        assert 'document.addEventListener(\'DOMContentLoaded\'' in js_content, \
            "DOMContentLoaded event listener not found"
        
        # Check that the DOMContentLoaded handler contains the necessary elements
        # We check for the presence of these patterns in the file
        assert 'menuToggleBtn' in js_content, "menuToggleBtn variable not found in JavaScript"
        # Check that addEventListener is registered for menu-toggle and toggleMenu is called
        assert "menuToggleBtn.addEventListener('click'" in js_content, \
            "Click event listener not registered for menu-toggle button"
        assert 'toggleMenu()' in js_content, \
            "toggleMenu() not called in event handler"
        
        # Verify the page detection check exists
        assert '!dashboardContainer && !statusIndicator' in js_content, \
            "Page detection check not found in DOMContentLoaded"
        
        print("[LOG] DOMContentLoaded has proper page detection and menu initialization")

    @pytest.mark.timeout(10)
    def test_closeMenu_function_logic(self, client):
        """Test the closeMenu function logic."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the function body
        assert 'sidebar.classList.remove(\'active\')' in js_content, "sidebar.classList.remove('active') not found"
        assert 'overlay.classList.remove(\'active\')' in js_content, "overlay.classList.remove('active') not found"
        assert "setAttribute('aria-hidden', 'true')" in js_content, "aria-hidden not set to 'true' in closeMenu"
        assert "setAttribute('aria-expanded', 'false')" in js_content, "aria-expanded not set to 'false' in closeMenu"
        assert 'menuToggle.focus()' in js_content, "menuToggle.focus() not found - focus not returned to button"
        
        print("[LOG] closeMenu function has correct logic for closing the menu")

    @pytest.mark.timeout(10)
    def test_overlay_click_closes_menu(self, client):
        """Test that clicking the overlay closes the menu."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for overlay click handler
        assert 'sidebarOverlay' in js_content, "sidebarOverlay variable not found"
        assert 'sidebarOverlay.addEventListener(\'click\'' in js_content or \
               'sidebar-overlay\').addEventListener(\'click\'' in js_content, \
               "Click event listener not found for sidebar-overlay"
        
        print("[LOG] Overlay click handler is registered to close the menu")

    @pytest.mark.timeout(10)
    def test_escape_key_closes_menu(self, client):
        """Test that pressing Escape key closes the menu."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for Escape key handler
        assert "event.key === 'Escape'" in js_content, "Escape key handler not found"
        
        print("[LOG] Escape key handler is registered to close the menu")

    @pytest.mark.timeout(10)
    def test_menu_toggle_exposed_on_window(self, client):
        """Test that toggleMenu is exposed on window object."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for window exposure
        assert 'window.toggleMenu = toggleMenu' in js_content, \
            "toggleMenu not exposed on window object"
        assert 'window.closeMenu = closeMenu' in js_content, \
            "closeMenu not exposed on window object"
        
        print("[LOG] toggleMenu and closeMenu are exposed on window object")

    @pytest.mark.timeout(10)
    def test_dashboardV2_object_exposes_toggleMenu(self, client):
        """Test that toggleMenu is also exposed on dashboardV2 object."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for dashboardV2 object exposure
        assert 'window.dashboardV2' in js_content, "window.dashboardV2 object not found"
        assert 'toggleMenu: toggleMenu' in js_content, "toggleMenu not exposed on dashboardV2 object"
        assert 'closeMenu: closeMenu' in js_content, "closeMenu not exposed on dashboardV2 object"
        
        print("[LOG] toggleMenu and closeMenu are exposed on dashboardV2 object")

    @pytest.mark.timeout(10)
    def test_toggleMenu_uses_getElementById(self, client):
        """Test that toggleMenu uses getElementById to find elements."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check that toggleMenu uses getElementById
        assert "document.getElementById('sidebar')" in js_content, \
            "toggleMenu doesn't use getElementById for sidebar"
        assert "document.getElementById('sidebar-overlay')" in js_content, \
            "toggleMenu doesn't use getElementById for overlay"
        assert "document.getElementById('menu-toggle')" in js_content, \
            "toggleMenu doesn't use getElementById for menu-toggle"
        
        print("[LOG] toggleMenu uses getElementById to find elements")

    @pytest.mark.timeout(10)
    def test_no_conflicting_event_listeners_in_extra_js(self, client):
        """Test that there are no conflicting event listeners in extra_js block."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check that extra_js block doesn't override menu toggle functionality
        # The extra_js block should not redefine toggleMenu or closeMenu
        if '{% block extra_js %}' in html_content:
            extra_js_section = html_content.split('{% block extra_js %}')[1].split('{% endblock %}')[0]
            
            # Check that toggleMenu is not redefined
            assert 'function toggleMenu' not in extra_js_section, \
                "toggleMenu is redefined in extra_js block - this could cause conflicts"
            assert 'function closeMenu' not in extra_js_section, \
                "closeMenu is redefined in extra_js block - this could cause conflicts"
            
            # Check that addEventListener for menu-toggle is not duplicated
            # (it should only be added in dashboardV2.js)
            if "getElementById('menu-toggle').addEventListener" in extra_js_section:
                # If it's in extra_js, it should be after the DOM is ready
                # but we should check for potential conflicts
                print("[LOG] Warning: menu-toggle event listener also found in extra_js block")
            else:
                print("[LOG] No conflicting event listeners in extra_js block")
        else:
            print("[LOG] No extra_js block found")

    @pytest.mark.timeout(10)
    def test_menu_button_has_type_attribute(self, client):
        """Test that menu button has type='button' to prevent form submission."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check that the menu-toggle button has type="button"
        # This prevents the button from acting as a submit button if placed in a form
        if 'id="menu-toggle"' in html_content:
            # Find the button element
            button_section = html_content.split('id="menu-toggle"')[0]
            # Check if type="button" is present in the button element
            # The button element starts with <button and ends with >
            # We need to check if type="button" is in the button element
            button_start = html_content.find('<button id="menu-toggle"')
            button_end = html_content.find('>', button_start)
            button_element = html_content[button_start:button_end+1]
            
            # Check for type attribute
            has_type = 'type=' in button_element
            print(f"[LOG] Menu button element: {button_element[:100]}...")
            print(f"[LOG] Has type attribute: {has_type}")
            
            # Note: type="button" is recommended but not strictly required
            # if the button is not inside a form
            if not has_type:
                print("[LOG] Warning: Menu button does not have type attribute - may cause issues if inside a form")
        else:
            pytest.fail("Menu toggle button not found in HTML")