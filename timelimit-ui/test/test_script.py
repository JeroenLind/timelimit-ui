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
    
    required_packages = ['requests', 'bcrypt']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ Python package '{package}' is available")
        except ImportError:
            print(f"❌ Python package '{package}' is NOT available")
            missing_packages.append(package)
    
    return len(missing_packages) == 0

def test_script_structure():
    """Test if the script has the required structure."""
    print("\n=== Testing Script Structure ===")
    
    script_path = str(Path(__file__).parent / "start_test_environment.py")
    
    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        return False
    
    try:
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check for essential functions
        required_functions = [
            'def setup_environment',
            'def start_web_server',
            'def start_frontend_components',
            'def check_server_health',
            'def run_test_suite',
            'def print_startup_info',
            'def cleanup',
            'def main'
        ]
        
        missing_functions = []
        for func in required_functions:
            if func not in content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"❌ Missing functions: {', '.join(missing_functions)}")
            return False
        else:
            print("✅ All required functions are present")
        
        # Check for essential imports
        required_imports = ['import os', 'import sys', 'import subprocess', 'import time']
        missing_imports = []
        
        for imp in required_imports:
            if imp not in content:
                missing_imports.append(imp)
        
        if missing_imports:
            print(f"❌ Missing imports: {', '.join(missing_imports)}")
            return False
        else:
            print("✅ All required imports are present")
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading script: {e}")
        return False

def test_configuration_files():
    """Test if configuration files are properly set up."""
    print("\n=== Testing Configuration Files ===")
    
    # Test config.yaml
    config_path = str(Path(__file__).parent / "config.yaml")
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        # Check for essential config sections
        required_sections = ['name:', 'description:', 'version:', 'slug:', 'arch:', 'init:', 'image:', 'ingress:', 'ingress_port:', 'panel_icon:', 'panel_title:', 'panel_admin:', 'options:', 'schema:']
        
        missing_sections = []
        for section in required_sections:
            if section not in config_content:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing config sections: {', '.join(missing_sections)}")
            return False
        else:
            print("✅ Config file has all required sections")
        
    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False
    
    # Test options.json
    options_path = str(Path(__file__).parent / "data" / "options.json")
    if not os.path.exists(options_path):
        print(f"❌ Options file not found: {options_path}")
        return False
    
    try:
        with open(options_path, 'r') as f:
            options = json.load(f)
        
        # Check for required options
        required_options = ['server_url', 'logging_mode']
        
        missing_options = []
        for option in required_options:
            if option not in options:
                missing_options.append(option)
        
        if missing_options:
            print(f"❌ Missing options: {', '.join(missing_options)}")
            return False
        else:
            print("✅ Options file has all required options")
        
    except Exception as e:
        print(f"❌ Error reading options file: {e}")
        return False
    
    return True

def test_directory_structure():
    """Test if the directory structure is correct."""
    print("\n=== Testing Directory Structure ===")
    
    # Check if test directory exists
    test_dir = Path(__file__).parent
    if not os.path.exists(test_dir):
        print(f"❌ Test directory not found: {test_dir}")
        return False
    
    print("✅ Test directory exists")
    
    # Check if data directory exists
    data_dir = Path(__file__).parent / "data"
    if not os.path.exists(data_dir):
        print(f"❌ Data directory not found: {data_dir}")
        return False
    
    print("✅ Data directory exists")
    
    # Check if logs directory exists
    logs_dir = Path(__file__).parent / "logs"
    if not os.path.exists(logs_dir):
        print(f"❌ Logs directory not found: {logs_dir}")
        return False
    
    print("✅ Logs directory exists")
    
    # Check if options.json exists in data directory
    options_path = str(Path(__file__).parent / "data" / "options.json")
    if not os.path.exists(options_path):
        print(f"❌ Options file not found in data directory: {options_path}")
        return False
    
    print("✅ Options file exists in data directory")
    
    return True

def test_script_syntax():
    """Test if the script has valid Python syntax."""
    print("\n=== Testing Script Syntax ===")
    
    script_path = str(Path(__file__).parent / "start_test_environment.py")
    
    try:
        # Try to compile the script
        with open(script_path, 'r') as f:
            content = f.read()
        
        compile(content, script_path, 'exec')
        print("✅ Script has valid Python syntax")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in script: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking script syntax: {e}")
        return False

def test_documentation():
    """Test if documentation is present."""
    print("\n=== Testing Documentation ===")
    
    doc_path = Path(__file__).parent / "TEST_ENVIRONMENT_SETUP.md"
    
    if not os.path.exists(doc_path):
        print(f"❌ Documentation not found: {doc_path}")
        return False
    
    try:
        with open(doc_path, 'r') as f:
            content = f.read()
        
        # Check for essential documentation sections
        required_sections = ['# TimeLimit UI Test Environment Setup', '## Overview', '## Quick Start', '## Configuration', '## Usage', '## Testing', '## Troubleshooting', '## Benefits of Local Development', '## Next Steps', '## Conclusion']
        
        missing_sections = []
        for section in required_sections:
            if section not in content:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing documentation sections: {', '.join(missing_sections)}")
            return False
        else:
            print("✅ Documentation has all required sections")
        
    except Exception as e:
        print(f"❌ Error reading documentation: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("🚀 Testing TimeLimit UI Test Environment")
    print("="*60)
    
    # Change to the timelimit-ui directory
    os.chdir("timelimit-ui")
    
    # Run all tests
    tests = [
        ("Dependencies", test_dependencies),
        ("Script Structure", test_script_structure),
        ("Configuration Files", test_configuration_files),
        ("Directory Structure", test_directory_structure),
        ("Script Syntax", test_script_syntax),
        ("Documentation", test_documentation)
    ]
    
    results = []
    for test_name, test_function in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        
        try:
            result = test_function()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
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
        print("1. Run 'python test/start_test_environment.py' to start the test environment")
        print("2. Open the dashboard in your browser: http://localhost:8099")
        print("3. Check log files in 'test/data/logs/timelimit-ui.log'")
        return 0
    else:
        print(f"\n❌ {total - passed} tests failed.")
        print("Please review the failed tests and fix any issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())