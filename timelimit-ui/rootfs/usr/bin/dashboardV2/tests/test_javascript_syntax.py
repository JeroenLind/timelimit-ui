"""
Test JavaScript syntax validation for dashboardV2.js

This test ensures that the JavaScript file has valid syntax and can be parsed
by Node.js. This catches syntax errors that would otherwise only be discovered
in the browser console.
"""

import subprocess
import os
import pytest


class TestJavaScriptSyntax:
    """Test JavaScript syntax validation."""

    def test_dashboard_v2_js_syntax(self):
        """Verify dashboardV2.js has valid JavaScript syntax."""
        js_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'js', 'dashboardV2.js'
        )
        
        # Check if file exists
        assert os.path.exists(js_file), f"JavaScript file not found: {js_file}"
        
        # Run node --check to validate syntax
        result = subprocess.run(
            ['node', '--check', js_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # node --check returns 0 for valid syntax, non-zero for errors
        assert result.returncode == 0, (
            f"JavaScript syntax error in {js_file}:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_dashboard_v2_js_is_valid_json_safe(self):
        """Verify dashboardV2.js can be parsed as a valid JavaScript file."""
        js_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'js', 'dashboardV2.js'
        )
        
        # Read the file and check it's not empty
        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert len(content) > 0, "JavaScript file is empty"
        
        # Check for basic JavaScript structure
        assert '(function()' in content or 'function' in content, (
            "JavaScript file should contain function definitions"
        )
        
        # Check for balanced braces (basic sanity check)
        open_braces = content.count('{')
        close_braces = content.count('}')
        assert open_braces == close_braces, (
            f"Unbalanced braces in JavaScript file: "
            f"{open_braces} opening, {close_braces} closing"
        )
        
        # Check for balanced parentheses (basic sanity check)
        open_parens = content.count('(')
        close_parens = content.count(')')
        assert open_parens == close_parens, (
            f"Unbalanced parentheses in JavaScript file: "
            f"{open_parens} opening, {close_parens} closing"
        )