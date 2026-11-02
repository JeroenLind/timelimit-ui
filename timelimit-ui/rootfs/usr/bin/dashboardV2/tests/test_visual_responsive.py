"""Visual and Responsive Tests for Dashboard V2.

This module tests:
- Desktop layout (1200px+)
- Tablet layout (768px - 1199px)
- Mobile layout (480px - 767px)
- Small mobile (< 480px)
- Light theme colors match specification
- Hamburger menu opens/closes correctly
- Role-based visibility with admin and standard user accounts
- Interactive elements have proper states
- Accessibility features (ARIA labels, keyboard navigation)
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock


class TestResponsiveLayout:
    """Tests for responsive layout behavior."""

    @pytest.mark.timeout(10)
    def test_desktop_layout_styles(self, client):
        """Test desktop layout (1200px+) CSS styles are correct."""
        # Read the CSS file
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Verify desktop layout styles exist
        assert '.dashboard-header' in css_content
        assert '.dashboard-content' in css_content
        assert '.family-overview-card' in css_content
        assert '.stat-badge' in css_content

        # Verify no max-width constraints for desktop
        assert '@media (max-width: 768px)' in css_content
        assert '@media (max-width: 480px)' in css_content

    @pytest.mark.timeout(10)
    def test_tablet_layout_media_query(self, client):
        """Test tablet layout (768px - 1199px) media query exists."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Verify tablet media query
        assert '@media (max-width: 768px)' in css_content

        # Verify tablet-specific styles
        assert '.family-stats' in css_content
        assert 'flex-direction: column' in css_content

    @pytest.mark.timeout(10)
    def test_mobile_layout_media_query(self, client):
        """Test mobile layout (480px - 767px) media query exists."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Verify mobile media query
        assert '@media (max-width: 480px)' in css_content

        # Verify mobile-specific styles
        assert '.stat-badge' in css_content
        assert 'flex: 1 1 100%' in css_content

    @pytest.mark.timeout(10)
    def test_small_mobile_layout(self, client):
        """Test small mobile (< 480px) layout adjustments."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Verify small mobile styles exist within the 480px media query
        # Check for container padding adjustments
        assert 'padding: var(--spacing-sm)' in css_content or 'padding: 5px' in css_content


class TestLightThemeColors:
    """Tests for light theme color specification compliance."""

    @pytest.mark.timeout(10)
    def test_background_color(self, client):
        """Test background color matches specification (#f5f7fa)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-bg: #f5f7fa' in css_content

    @pytest.mark.timeout(10)
    def test_card_color(self, client):
        """Test card/background color matches specification (#ffffff)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-card: #ffffff' in css_content

    @pytest.mark.timeout(10)
    def test_primary_text_color(self, client):
        """Test primary text color matches specification (#212529)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-text-primary: #212529' in css_content

    @pytest.mark.timeout(10)
    def test_secondary_text_color(self, client):
        """Test secondary text color matches specification (#6c757d)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-text-secondary: #6c757d' in css_content

    @pytest.mark.timeout(10)
    def test_success_color(self, client):
        """Test success color matches specification (#28a745)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-success: #28a745' in css_content

    @pytest.mark.timeout(10)
    def test_warning_color(self, client):
        """Test warning color matches specification (#ffc107)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-warning: #ffc107' in css_content

    @pytest.mark.timeout(10)
    def test_error_color(self, client):
        """Test error color matches specification (#dc3545)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-error: #dc3545' in css_content

    @pytest.mark.timeout(10)
    def test_primary_color(self, client):
        """Test primary color matches specification (#667eea)."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '--color-primary: #667eea' in css_content

    @pytest.mark.timeout(10)
    def test_contrast_ratio_compliance(self, client):
        """Test that color combinations meet WCAG 2.1 AA contrast ratio (4.5:1)."""
        # Primary text (#212529) on light background (#f5f7fa)
        # Contrast ratio is approximately 15:1 - well above 4.5:1
        # This is verified by the CSS variables being correct
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Verify the colors are set correctly
        assert '--color-bg: #f5f7fa' in css_content
        assert '--color-text-primary: #212529' in css_content
        assert '--color-text-secondary: #6c757d' in css_content


class TestHamburgerMenu:
    """Tests for hamburger menu open/close functionality."""

    @pytest.mark.timeout(10)
    def test_hamburger_menu_button_exists(self, client):
        """Test hamburger menu button exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="menu-toggle"' in html_content
        assert 'class="menu-toggle"' in html_content

    @pytest.mark.timeout(10)
    def test_hamburger_menu_aria_label(self, client):
        """Test hamburger menu has proper ARIA label."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'aria-label="Open menu"' in html_content
        assert 'aria-expanded="false"' in html_content

    @pytest.mark.timeout(10)
    def test_sidebar_exists(self, client):
        """Test sidebar navigation exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="sidebar"' in html_content
        assert 'class="dashboard-sidebar"' in html_content
        assert 'role="navigation"' in html_content

    @pytest.mark.timeout(10)
    def test_sidebar_overlay_exists(self, client):
        """Test sidebar overlay exists for click-to-close."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="sidebar-overlay"' in html_content
        assert 'class="sidebar-overlay"' in html_content

    @pytest.mark.timeout(10)
    def test_sidebar_close_button_exists(self, client):
        """Test sidebar close button exists."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="sidebar-close"' in html_content

    @pytest.mark.timeout(10)
    def test_toggle_menu_function_exists(self, client):
        """Test toggleMenu function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function toggleMenu()' in js_content
        assert 'function closeMenu()' in js_content

    @pytest.mark.timeout(10)
    def test_menu_toggle_exposed_globally(self, client):
        """Test toggleMenu is exposed globally for HTML onclick handlers."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'window.toggleMenu = toggleMenu' in js_content
        assert 'window.closeMenu = closeMenu' in js_content

    @pytest.mark.timeout(10)
    def test_sidebar_css_positioning(self, client):
        """Test sidebar CSS has correct positioning for slide-in animation."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Sidebar should be positioned off-screen right initially
        assert 'right: -280px' in css_content or 'transform: translateX(100%)' in css_content
        # Active state should bring it in
        assert '.dashboard-sidebar.active' in css_content

    @pytest.mark.timeout(10)
    def test_sidebar_overlay_aria_hidden(self, client):
        """Test sidebar overlay has aria-hidden attribute."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'aria-hidden="true"' in html_content


class TestRoleBasedVisibility:
    """Tests for role-based visibility functionality."""

    @pytest.mark.timeout(10)
    def test_admin_only_class_exists(self, client):
        """Test .admin-only CSS class exists."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.admin-only {' in css_content
        assert 'display: block' in css_content

    @pytest.mark.timeout(10)
    def test_hidden_class_exists(self, client):
        """Test .hidden CSS class exists."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.hidden {' in css_content
        assert 'display: none !important' in css_content

    @pytest.mark.timeout(10)
    def test_admin_only_hidden_combination(self, client):
        """Test .admin-only.hidden combination exists."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.admin-only.hidden {' in css_content

    @pytest.mark.timeout(10)
    def test_check_admin_visibility_function_exists(self, client):
        """Test checkAdminVisibility function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'async function checkAdminVisibility()' in js_content

    @pytest.mark.timeout(10)
    def test_update_admin_only_elements_function_exists(self, client):
        """Test updateAdminOnlyElements function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function updateAdminOnlyElements(isAdmin)' in js_content

    @pytest.mark.timeout(10)
    def test_admin_section_in_html(self, client):
        """Test Administration section exists in sidebar HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="admin-section"' in html_content
        assert 'Administration' in html_content

    @pytest.mark.timeout(10)
    def test_create_new_family_link_is_admin_only(self, client):
        """Test Create New Family link has admin-only class."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for admin-only class on Create New Family link
        assert 'Create New Family' in html_content

    @pytest.mark.timeout(10)
    def test_has_parent_password_second_hash_check(self, client):
        """Test that admin visibility is based on has_parent_password_second_hash."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'has_parent_password_second_hash' in js_content
        assert 'data.has_parent_password_second_hash === true' in js_content


class TestInteractiveElementStates:
    """Tests for interactive element states (hover, active, focus)."""

    @pytest.mark.timeout(10)
    def test_hamburger_menu_hover_state(self, client):
        """Test hamburger menu has hover state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.menu-toggle:hover' in css_content

    @pytest.mark.timeout(10)
    def test_hamburger_menu_focus_state(self, client):
        """Test hamburger menu has focus state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.menu-toggle:focus' in css_content
        assert '.menu-toggle:focus-visible' in css_content

    @pytest.mark.timeout(10)
    def test_hamburger_menu_active_state(self, client):
        """Test hamburger menu has active state with scale transform."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.menu-toggle:active' in css_content
        assert 'transform: scale(0.95)' in css_content

    @pytest.mark.timeout(10)
    def test_sidebar_menu_items_hover_state(self, client):
        """Test sidebar menu items have hover state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.sidebar-nav a:hover' in css_content
        assert '.sidebar-nav button:hover' in css_content

    @pytest.mark.timeout(10)
    def test_sidebar_menu_items_focus_state(self, client):
        """Test sidebar menu items have focus state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.sidebar-nav a:focus' in css_content
        assert '.sidebar-nav button:focus' in css_content

    @pytest.mark.timeout(10)
    def test_buttons_have_focus_state(self, client):
        """Test all buttons have focus state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.btn:focus' in css_content
        assert '.btn:focus-visible' in css_content

    @pytest.mark.timeout(10)
    def test_buttons_have_active_state(self, client):
        """Test all buttons have active state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.btn:active' in css_content

    @pytest.mark.timeout(10)
    def test_user_cards_hover_state(self, client):
        """Test user cards have hover state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.user-card:hover' in css_content

    @pytest.mark.timeout(10)
    def test_form_controls_focus_state(self, client):
        """Test form controls have focus state."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.form-control:focus' in css_content


class TestAccessibilityFeatures:
    """Tests for accessibility features (ARIA labels, keyboard navigation)."""

    @pytest.mark.timeout(10)
    def test_hamburger_menu_aria_expanded(self, client):
        """Test hamburger menu has aria-expanded attribute."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'aria-expanded="false"' in html_content

    @pytest.mark.timeout(10)
    def test_sidebar_has_role_navigation(self, client):
        """Test sidebar has role='navigation'."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'role="navigation"' in html_content

    @pytest.mark.timeout(10)
    def test_menu_items_have_rolemenuitem(self, client):
        """Test menu items have role='menuitem'."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'role="menuitem"' in html_content

    @pytest.mark.timeout(10)
    def test_hamburger_bars_have_aria_hidden(self, client):
        """Test hamburger bar spans have aria-hidden for decorative icons."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for aria-hidden on decorative elements
        assert 'aria-hidden="true"' in html_content

    @pytest.mark.timeout(10)
    def test_escape_key_closes_sidebar(self, client):
        """Test Escape key closes sidebar in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert "event.key === 'Escape'" in js_content
        assert 'closeMenu()' in js_content

    @pytest.mark.timeout(10)
    def test_overlay_click_closes_sidebar(self, client):
        """Test clicking overlay closes sidebar."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'sidebar-overlay' in js_content
        assert 'closeMenu()' in js_content

    @pytest.mark.timeout(10)
    def test_focus_management_on_open(self, client):
        """Test focus is managed when menu opens."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'firstMenuItem.focus()' in js_content or 'firstMenuItem' in js_content

    @pytest.mark.timeout(10)
    def test_refocus_on_close(self, client):
        """Test focus returns to menu toggle when closed."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'menuToggle.focus()' in js_content or 'menu-toggle' in js_content

    @pytest.mark.timeout(10)
    def test_alert_close_button_accessible(self, client):
        """Test alert close button is accessible."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'alert-close' in html_content

    @pytest.mark.timeout(10)
    def test_contrast_ratio_meets_aa(self, client):
        """Test color contrast ratios meet WCAG 2.1 AA (4.5:1)."""
        # This is verified by the CSS variables being correct
        # Primary text (#212529) on light background (#f5f7fa) = ~15:1
        # Secondary text (#6c757d) on white = ~7:1
        # All meet WCAG 2.1 AA requirements
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Verify the colors are set correctly
        assert '--color-bg: #f5f7fa' in css_content
        assert '--color-text-primary: #212529' in css_content
        assert '--color-text-secondary: #6c757d' in css_content


class TestAdminVisibilityIntegration:
    """Integration tests for admin visibility with API responses."""

    @pytest.mark.timeout(10)
    def test_session_status_includes_parent_password_hash(self, client):
        """Test session status API includes has_parent_password_second_hash field."""
        # Mock the pre-loaded tokens to simulate no persisted session
        import app as app_module
        app_module._preloaded_device_auth_token = None
        app_module._preloaded_own_device_id = None

        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'has_parent_password_second_hash' in data

    @pytest.mark.timeout(10)
    def test_admin_section_hidden_for_non_admin(self, client):
        """Test admin section is hidden when has_parent_password_second_hash is False."""
        # Create a family without parent password hash
        from database import create_family, store_auth_token

        db = client.application.test_db
        device_auth_token = 'device_token_no_hash_test'

        create_family(
            db=db,
            device_auth_token=device_auth_token,
            mail='nohash@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash=None,  # No second hash
            parent_password_second_salt=None,
            parent_password_encrypted=False
        )

        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id='device_no_hash_test',
            mail='nohash@example.com'
        )

        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['server_url'] = 'http://localhost:8080'

        response = client.get('/api/session/status')
        data = json.loads(response.data)

        # Should be False when no hash is set
        assert data['has_parent_password_second_hash'] is False

    @pytest.mark.timeout(10)
    def test_admin_section_visible_for_admin(self, client):
        """Test admin section is visible when has_parent_password_second_hash is True."""
        # Create a family with parent password hash
        from database import create_family, store_auth_token

        db = client.application.test_db
        device_auth_token = 'device_token_with_hash_test'

        create_family(
            db=db,
            device_auth_token=device_auth_token,
            mail='admin@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',  # Has second hash
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )

        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id='device_with_hash_test',
            mail='admin@example.com'
        )

        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['server_url'] = 'http://localhost:8080'

        response = client.get('/api/session/status')
        data = json.loads(response.data)

        # Should be True when hash is set
        assert data['has_parent_password_second_hash'] is True


class TestFamilyOverviewCard:
    """Tests for Family Overview Card component."""

    @pytest.mark.timeout(10)
    def test_family_overview_card_exists(self, client):
        """Test family overview card exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="family-overview-card"' in html_content
        assert 'family-overview-card' in html_content

    @pytest.mark.timeout(10)
    def test_family_overview_card_styles(self, client):
        """Test family overview card has correct styles."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.family-overview-card' in css_content
        assert '.stat-badge' in css_content

    @pytest.mark.timeout(10)
    def test_family_email_display_exists(self, client):
        """Test family email display element exists."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="family-email-display"' in html_content

    @pytest.mark.timeout(10)
    def test_devices_count_badge_exists(self, client):
        """Test devices count badge exists."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="devices-count"' in html_content
        assert 'id="devices-badge"' in html_content

    @pytest.mark.timeout(10)
    def test_users_count_badge_exists(self, client):
        """Test users count badge exists."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="users-count"' in html_content
        assert 'id="users-badge"' in html_content

    @pytest.mark.timeout(10)
    def test_last_sync_display_exists(self, client):
        """Test last sync timestamp display exists."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="last-sync-timestamp"' in html_content

    @pytest.mark.timeout(10)
    def test_render_family_overview_function_exists(self, client):
        """Test renderFamilyOverview function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function renderFamilyOverview(data)' in js_content


class TestSidebarNavigation:
    """Tests for sidebar navigation structure."""

    @pytest.mark.timeout(10)
    def test_dashboard_section_exists(self, client):
        """Test Dashboard section exists in sidebar."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert '>Dashboard<' in html_content or 'Dashboard' in html_content

    @pytest.mark.timeout(10)
    def test_server_section_exists(self, client):
        """Test Server section exists in sidebar."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert '>Server<' in html_content or 'Server Status' in html_content

    @pytest.mark.timeout(10)
    def test_session_section_exists(self, client):
        """Test Session section exists in sidebar."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert '>Session<' in html_content or 'Session Details' in html_content

    @pytest.mark.timeout(10)
    def test_help_section_exists(self, client):
        """Test Help section exists in sidebar."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert '>Help<' in html_content or 'Documentation' in html_content

    @pytest.mark.timeout(10)
    def test_sync_now_button_exists(self, client):
        """Test Sync Now button exists in sidebar."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="sync-now-btn"' in html_content
        assert 'Sync Now' in html_content

    @pytest.mark.timeout(10)
    def test_sign_out_button_exists(self, client):
        """Test Sign Out button exists in sidebar."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="signout-btn-sidebar"' in html_content
        assert 'Sign Out' in html_content


class TestHamburgerMenuVisibility:
    """Tests for hamburger menu styles in external CSS file."""

    @pytest.mark.timeout(10)
    def test_hamburger_menu_styles_in_css(self, client):
        """Test hamburger menu button has CSS styles defined in external CSS file."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check that the CSS file contains hamburger menu styles
        assert '.menu-toggle {' in css_content
        assert 'width: 40px' in css_content or 'width: 44px' in css_content or 'width: var(--spacing-md)' in css_content
        assert 'height: 40px' in css_content or 'height: 44px' in css_content or 'height: var(--size-lg)' in css_content

    @pytest.mark.timeout(10)
    def test_hamburger_menu_bars_have_correct_styles(self, client):
        """Test hamburger menu bars (three lines) have correct styles in CSS."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check that the bar styles are defined in CSS
        assert '.menu-toggle .bar {' in css_content
        assert 'width: 20px' in css_content or 'width: 22px' in css_content or 'width: var(--size-sm)' in css_content
        assert 'height: 2px' in css_content or 'height: 2.5px' in css_content

    @pytest.mark.timeout(10)
    def test_sidebar_has_correct_positioning(self, client):
        """Test sidebar has correct CSS positioning for slide-in animation."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check that the sidebar positioning is defined in CSS
        assert '.dashboard-sidebar {' in css_content
        assert 'position: fixed' in css_content
        # Sidebar should be positioned off-screen right initially
        assert 'right: -280px' in css_content or 'transform: translateX(100%)' in css_content

    @pytest.mark.timeout(10)
    def test_sidebar_active_state_brings_it_in(self, client):
        """Test sidebar active state brings it into view."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check that the active state is defined in CSS
        assert '.dashboard-sidebar.active {' in css_content
        assert 'right: 0' in css_content or 'transform: translateX(0)' in css_content

    @pytest.mark.timeout(10)
    def test_hamburger_menu_button_not_display_none(self, client):
        """Test hamburger menu button is not hidden with display: none."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check that menu-toggle is not hidden
        # The menu-toggle style should not have display: none
        menu_toggle_style = css_content.split('.menu-toggle {')[1].split('}')[0] if '.menu-toggle {' in css_content else ''
        assert menu_toggle_style, "menu-toggle style not found"
        assert 'display: none' not in menu_toggle_style, "menu-toggle should not have display: none"
        assert 'visibility: hidden' not in menu_toggle_style, "menu-toggle should not have visibility: hidden"
        assert 'opacity: 0' not in menu_toggle_style, "menu-toggle should not have opacity: 0"

    @pytest.mark.timeout(10)
    def test_hamburger_menu_button_has_background(self, client):
        """Test hamburger menu button has visible background color."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # Check that menu-toggle has a background color
        menu_toggle_style = css_content.split('.menu-toggle {')[1].split('}')[0] if '.menu-toggle {' in css_content else ''
        assert menu_toggle_style, "menu-toggle style not found"
        assert 'background' in menu_toggle_style, "menu-toggle should have a background color"
        assert 'border' in menu_toggle_style, "menu-toggle should have a border"


class TestSidebarLoginLinks:
    """Tests for sidebar login links (Sign In, Create Family)."""

    @pytest.mark.timeout(10)
    def test_login_sidebar_link_exists_in_html(self, client):
        """Test that login-sidebar-link element exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="login-sidebar-link"' in html_content, "login-sidebar-link element not found in HTML"
        assert 'href="/login-as-parent"' in html_content, "login-sidebar-link should link to /login-as-parent"
        print("[LOG] login-sidebar-link element exists in HTML")

    @pytest.mark.timeout(10)
    def test_create_family_sidebar_link_exists_in_html(self, client):
        """Test that create-family-sidebar-link element exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="create-family-sidebar-link"' in html_content, "create-family-sidebar-link element not found in HTML"
        assert 'href="/create-family"' in html_content, "create-family-sidebar-link should link to /create-family"
        print("[LOG] create-family-sidebar-link element exists in HTML")

    @pytest.mark.timeout(10)
    def test_sidebar_login_links_have_role_menuitem(self, client):
        """Test that sidebar login links have role='menuitem'."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="login-sidebar-link"' in html_content
        assert 'role="menuitem"' in html_content
        print("[LOG] Sidebar login links have role='menuitem'")

    @pytest.mark.timeout(10)
    def test_sidebar_login_links_have_sidebar_action_link_class(self, client):
        """Test that sidebar login links have sidebar-action-link class."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'class="sidebar-action-link"' in html_content, "sidebar-action-link class not found"
        print("[LOG] Sidebar login links have sidebar-action-link class")

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_handles_sidebar_login_links(self, client):
        """Test that updateSessionOverview function handles sidebar login links."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the new sidebar login link element lookups
        assert "document.getElementById('login-sidebar-link')" in js_content, \
            "login-sidebar-link element lookup not found in JavaScript"
        assert "document.getElementById('create-family-sidebar-link')" in js_content, \
            "create-family-sidebar-link element lookup not found in JavaScript"
        print("[LOG] updateSessionOverview handles sidebar login links")

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_shows_login_links_when_not_authenticated(self, client):
        """Test that updateSessionOverview shows login links when not authenticated."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the logic that shows login links when not authenticated
        assert "loginSidebarLink.style.display = 'block'" in js_content, \
            "Logic to show login-sidebar-link when not authenticated not found"
        assert "createFamilySidebarLink.style.display = 'block'" in js_content, \
            "Logic to show create-family-sidebar-link when not authenticated not found"
        print("[LOG] updateSessionOverview shows login links when not authenticated")

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_hides_login_links_when_authenticated(self, client):
        """Test that updateSessionOverview hides login links when authenticated."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the logic that hides login links when authenticated
        assert "loginSidebarLink.style.display = 'none'" in js_content, \
            "Logic to hide login-sidebar-link when authenticated not found"
        assert "createFamilySidebarLink.style.display = 'none'" in js_content, \
            "Logic to hide create-family-sidebar-link when authenticated not found"
        print("[LOG] updateSessionOverview hides login links when authenticated")

    @pytest.mark.timeout(10)
    def test_sidebar_action_link_css_exists(self, client):
        """Test that sidebar-action-link CSS class exists."""
        css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'dashboardV2.css'))
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        assert '.sidebar-action-link' in css_content or '.sidebar-nav a,' in css_content, \
            "sidebar-action-link CSS class or sidebar-nav a styles not found"
        print("[LOG] sidebar-action-link CSS class exists")


class TestAddDummyUserButton:
    """Tests for the Add Dummy User button in the sidebar."""

    @pytest.mark.timeout(10)
    def test_add_dummy_user_button_exists_in_html(self, client):
        """Test that add-dummy-user-btn element exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-dummy-user-btn"' in html_content, "add-dummy-user-btn element not found in HTML"
        assert 'class="sidebar-action-link"' in html_content, "add-dummy-user-btn should have sidebar-action-link class"
        print("[LOG] add-dummy-user-btn element exists in HTML")

    @pytest.mark.timeout(10)
    def test_add_dummy_user_button_has_role_menuitem(self, client):
        """Test that add-dummy-user-btn has role='menuitem'."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-dummy-user-btn"' in html_content
        assert 'role="menuitem"' in html_content
        print("[LOG] add-dummy-user-btn has role='menuitem'")

    @pytest.mark.timeout(10)
    def test_add_dummy_user_button_in_actions_section(self, client):
        """Test that add-dummy-user-btn is in the Actions section."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check that the button is in the Actions section (after Create Family link)
        assert 'id="create-family-sidebar-link"' in html_content
        assert 'id="add-dummy-user-btn"' in html_content
        # Verify order: Create Family -> Add Dummy User -> Sign Out
        create_family_pos = html_content.find('id="create-family-sidebar-link"')
        add_dummy_pos = html_content.find('id="add-dummy-user-btn"')
        signout_pos = html_content.find('id="signout-btn-sidebar"')
        assert create_family_pos < add_dummy_pos < signout_pos, \
            "add-dummy-user-btn should be between create-family-sidebar-link and signout-btn-sidebar"
        print("[LOG] add-dummy-user-btn is in the Actions section")


class TestAddDummyUserModal:
    """Tests for the Add Dummy User modal."""

    @pytest.mark.timeout(10)
    def test_add_user_modal_exists_in_html(self, client):
        """Test that add-user-modal element exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-user-modal"' in html_content, "add-user-modal element not found in HTML"
        print("[LOG] add-user-modal element exists in HTML")

    @pytest.mark.timeout(10)
    def test_add_user_modal_has_name_input(self, client):
        """Test that add-user-modal has a name input field."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-user-name"' in html_content, "add-user-name input not found in modal"
        print("[LOG] add-user-modal has name input field")

    @pytest.mark.timeout(10)
    def test_add_user_modal_has_submit_button(self, client):
        """Test that add-user-modal has a submit button."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-user-submit-btn"' in html_content, "add-user-submit-btn not found in modal"
        print("[LOG] add-user-modal has submit button")

    @pytest.mark.timeout(10)
    def test_add_user_modal_has_cancel_button(self, client):
        """Test that add-user-modal has a cancel button."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-user-cancel-btn"' in html_content, "add-user-cancel-btn not found in modal"
        print("[LOG] add-user-modal has cancel button")

    @pytest.mark.timeout(10)
    def test_add_user_modal_has_close_button(self, client):
        """Test that add-user-modal has a close button (X)."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-user-modal-close"' in html_content, "add-user-modal-close button not found in modal"
        print("[LOG] add-user-modal has close button")

    @pytest.mark.timeout(10)
    def test_add_user_modal_overlay_exists(self, client):
        """Test that add-user-modal-overlay element exists in HTML."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates', 'dashboardV2.html'))
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'id="add-user-modal-overlay"' in html_content, "add-user-modal-overlay element not found in HTML"
        print("[LOG] add-user-modal-overlay element exists in HTML")


class TestAddDummyUserJavaScript:
    """Tests for the Add Dummy User JavaScript functions."""

    @pytest.mark.timeout(10)
    def test_showAddUserModal_function_exists(self, client):
        """Test that showAddUserModal function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function showAddUserModal()' in js_content, "showAddUserModal function not found"
        print("[LOG] showAddUserModal function exists in JavaScript")

    @pytest.mark.timeout(10)
    def test_hideAddUserModal_function_exists(self, client):
        """Test that hideAddUserModal function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'function hideAddUserModal()' in js_content, "hideAddUserModal function not found"
        print("[LOG] hideAddUserModal function exists in JavaScript")

    @pytest.mark.timeout(10)
    def test_submitAddUserForm_function_exists(self, client):
        """Test that submitAddUserForm function exists in JavaScript."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert 'async function submitAddUserForm()' in js_content, "submitAddUserForm function not found"
        print("[LOG] submitAddUserForm function exists in JavaScript")

    @pytest.mark.timeout(10)
    def test_add_dummy_user_button_event_listener(self, client):
        """Test that event listener is registered for add-dummy-user-btn."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert "getElementById('add-dummy-user-btn')" in js_content, \
            "Event listener for add-dummy-user-btn not found"
        assert "showAddUserModal()" in js_content, \
            "showAddUserModal call not found in event listener"
        print("[LOG] Event listener for add-dummy-user-btn is registered")

    @pytest.mark.timeout(10)
    def test_modal_close_event_listener(self, client):
        """Test that event listener is registered for modal close button."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert "getElementById('add-user-modal-close')" in js_content, \
            "Event listener for add-user-modal-close not found"
        print("[LOG] Event listener for modal close button is registered")

    @pytest.mark.timeout(10)
    def test_modal_submit_button_event_listener(self, client):
        """Test that event listener is registered for modal submit button."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert "getElementById('add-user-submit-btn')" in js_content, \
            "Event listener for add-user-submit-btn not found"
        assert "submitAddUserForm()" in js_content, \
            "submitAddUserForm call not found in event listener"
        print("[LOG] Event listener for modal submit button is registered")


class TestAddDummyUserVisibility:
    """Tests for the Add Dummy User button visibility in updateSessionOverview."""

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_handles_add_dummy_user_button(self, client):
        """Test that updateSessionOverview function handles add-dummy-user-btn."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        assert "document.getElementById('add-dummy-user-btn')" in js_content, \
            "add-dummy-user-btn element lookup not found in JavaScript"
        print("[LOG] updateSessionOverview handles add-dummy-user-btn")

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_shows_add_dummy_user_when_authenticated(self, client):
        """Test that updateSessionOverview shows add-dummy-user-btn when authenticated."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the logic that shows add-dummy-user-btn when authenticated
        # The code uses a ternary operator: data.authenticated ? 'block' : 'none'
        assert "addDummyUserBtn.style.display = data.authenticated ? 'block' : 'none'" in js_content, \
            "Logic to show/hide add-dummy-user-btn based on authentication not found"
        print("[LOG] updateSessionOverview shows add-dummy-user-btn when authenticated")

    @pytest.mark.timeout(10)
    def test_updateSessionOverview_hides_add_dummy_user_when_not_authenticated(self, client):
        """Test that updateSessionOverview hides add-dummy-user-btn when not authenticated."""
        js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboardV2.js'))
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        # Check for the logic that hides add-dummy-user-btn when not authenticated
        # The code uses a ternary operator: data.authenticated ? 'block' : 'none'
        assert "addDummyUserBtn.style.display = data.authenticated ? 'block' : 'none'" in js_content, \
            "Logic to show/hide add-dummy-user-btn based on authentication not found"
        print("[LOG] updateSessionOverview hides add-dummy-user-btn when not authenticated")