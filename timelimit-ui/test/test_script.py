#!/usr/bin/env python3
"""Test script to verify the TimeLimit UI test environment script."""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path


def test_dependencies():
    """Test if required Python packages are available."""
    print("=== Testing Dependencies ===")

    required_packages = ["requests", "bcrypt"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ Python package '{package}' is available")
        except ImportError:
            print(f"❌ Python package '{package}' is NOT available")
            missing_packages.append(package)

    assert len(missing_packages) == 0, f"Missing packages: {missing_packages}"


def test_script_structure():
    """Test if the script has the required structure."""
    print("\n=== Testing Script Structure ===")

    script_path = str(Path(__file__).parent / "start_test_environment.py")

    assert os.path.exists(script_path), f"Script not found: {script_path}"

    with open(script_path, "r") as f:
        content = f.read()

    # Check for essential functions
    required_functions = [
        "def setup_environment",
        "def start_web_server",
        "def start_frontend_components",
        "def check_server_health",
        "def run_test_suite",
        "def print_startup_info",
        "def cleanup",
        "def main",
    ]

    missing_functions = []
    for func in required_functions:
        if func not in content:
            missing_functions.append(func)

    assert len(missing_functions) == 0, f"Missing functions: {missing_functions}"
    print("✅ All required functions are present")

    # Check for essential imports
    required_imports = ["import os", "import sys", "import subprocess", "import time"]
    missing_imports = []

    for imp in required_imports:
        if imp not in content:
            missing_imports.append(imp)

    assert len(missing_imports) == 0, f"Missing imports: {missing_imports}"
    print("✅ All required imports are present")


def test_configuration_files():
    """Test if configuration files are properly set up."""
    print("\n=== Testing Configuration Files ===")

    # Test config.yaml
    config_path = str(Path(__file__).parent / "config.yaml")
    assert os.path.exists(config_path), f"Config file not found: {config_path}"

    with open(config_path, "r") as f:
        config_content = f.read()

    # Check for essential config sections
    required_sections = [
        "name:",
        "description:",
        "version:",
        "slug:",
        "arch:",
        "init:",
        "image:",
        "ingress:",
        "ingress_port:",
        "panel_icon:",
        "panel_title:",
        "panel_admin:",
        "options:",
        "schema:",
    ]

    missing_sections = []
    for section in required_sections:
        if section not in config_content:
            missing_sections.append(section)

    assert len(missing_sections) == 0, f"Missing config sections: {missing_sections}"
    print("✅ Config file has all required sections")

    # Test options.json
    options_path = str(Path(__file__).parent / "data" / "options.json")
    assert os.path.exists(options_path), f"Options file not found: {options_path}"

    with open(options_path, "r") as f:
        options = json.load(f)

    # Check for required options
    required_options = ["server_url", "logging_mode"]

    missing_options = []
    for option in required_options:
        if option not in options:
            missing_options.append(option)

    assert len(missing_options) == 0, f"Missing options: {missing_options}"
    print("✅ Options file has all required options")


def test_directory_structure():
    """Test if the directory structure is correct."""
    print("\n=== Testing Directory Structure ===")

    # Check if test directory exists
    test_dir = Path(__file__).parent
    assert os.path.exists(test_dir), f"Test directory not found: {test_dir}"
    print("✅ Test directory exists")

    # Check if data directory exists
    data_dir = Path(__file__).parent / "data"
    assert os.path.exists(data_dir), f"Data directory not found: {data_dir}"
    print("✅ Data directory exists")

    # Check if logs directory exists in data folder (created by start_test_environment.py)
    logs_dir = Path(__file__).parent / "data" / "logs"
    if os.path.exists(logs_dir):
        print("✅ Logs directory exists")
    else:
        print(
            "⚠️  Logs directory not found (will be created when test environment starts)"
        )

    # Check if options.json exists in data directory
    options_path = str(Path(__file__).parent / "data" / "options.json")
    assert os.path.exists(options_path), (
        f"Options file not found in data directory: {options_path}"
    )
    print("✅ Options file exists in data directory")


def test_script_syntax():
    """Test if the script has valid Python syntax."""
    print("\n=== Testing Script Syntax ===")

    script_path = str(Path(__file__).parent / "start_test_environment.py")

    with open(script_path, "r") as f:
        content = f.read()

    try:
        compile(content, script_path, "exec")
        print("✅ Script has valid Python syntax")
    except SyntaxError as e:
        print(f"❌ Syntax error in script: {e}")
        raise
    except Exception as e:
        print(f"❌ Error checking script syntax: {e}")
        raise


def test_documentation():
    """Test if documentation is present."""
    print("\n=== Testing Documentation ===")

    doc_path = Path(__file__).parent / "TEST_ENVIRONMENT_SETUP.md"

    assert os.path.exists(doc_path), f"Documentation not found: {doc_path}"

    with open(doc_path, "r") as f:
        content = f.read()

    # Check for essential documentation sections
    required_sections = [
        "# TimeLimit UI Test Environment Setup",
        "## Overview",
        "## Quick Start",
        "## Configuration",
        "## Usage",
        "## Testing",
        "## Troubleshooting",
        "## Benefits of Local Development",
        "## Next Steps",
        "## Conclusion",
    ]

    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)

    assert len(missing_sections) == 0, (
        f"Missing documentation sections: {missing_sections}"
    )
    print("✅ Documentation has all required sections")


def main():
    """Run all tests."""
    print("🚀 Testing TimeLimit UI Test Environment")
    print("=" * 60)

    # Change to the timelimit-ui directory
    os.chdir("timelimit-ui")

    # Run all tests
    tests = [
        ("Dependencies", test_dependencies),
        ("Script Structure", test_script_structure),
        ("Configuration Files", test_configuration_files),
        ("Directory Structure", test_directory_structure),
        ("Script Syntax", test_script_syntax),
        ("Documentation", test_documentation),
    ]

    results = []
    for test_name, test_function in tests:
        print(f"\n{'=' * 60}")
        print(f"Running: {test_name}")
        print(f"{'=' * 60}")

        try:
            result = test_function()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))

    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print(f"{'=' * 60}")

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! The test environment is ready.")
        print("\nNext steps:")
        print(
            "1. Run 'python test/start_test_environment.py' to start the test environment"
        )
        print("2. Open the dashboard in your browser: http://localhost:8099")
        print("3. Check log files in 'test/data/logs/timelimit-ui.log'")
        return 0
    else:
        print(f"\n❌ {total - passed} tests failed.")
        print("Please review the failed tests and fix any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
