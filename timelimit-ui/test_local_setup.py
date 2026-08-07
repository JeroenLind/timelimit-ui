#!/usr/bin/env python3
"""Test script to verify the TimeLimit UI local development setup."""

import os
import sys
import json
import subprocess
import time
import requests

def check_file_exists(path, description):
    """Check if a file exists and return status."""
    if os.path.exists(path):
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} - NOT FOUND")
        return False

def check_directory_exists(path, description):
    """Check if a directory exists and return status."""
    if os.path.exists(path) and os.path.isdir(path):
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} - NOT FOUND")
        return False

def check_python_dependencies():
    """Check if required Python packages are available."""
    print("\n=== Checking Python Dependencies ===")
    
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

def check_config_file():
    """Check if configuration files are properly set up."""
    print("\n=== Checking Configuration Files ===")
    
    config_path = "timelimit-ui/config.yaml"
    options_path = "timelimit-ui/data/options.json"
    
    config_ok = check_file_exists(config_path, "Configuration file")
    
    # Check if options.json exists or can be created
    if os.path.exists(options_path):
        print(f"✅ Options file exists: {options_path}")
        try:
            with open(options_path, 'r') as f:
                config = json.load(f)
                print(f"✅ Options file is valid JSON")
                print(f"   Server URL: {config.get('server_url', 'NOT SET')}")
                print(f"   Logging mode: {config.get('logging_mode', 'NOT SET')}")
        except Exception as e:
            print(f"❌ Options file is invalid JSON: {e}")
            config_ok = False
    else:
        print(f"⚠️ Options file does not exist: {options_path}")
        print(f"   This is expected for first-time setup")
    
    return config_ok

def check_log_directory():
    """Check if log directory is set up."""
    print("\n=== Checking Log Directory ===")
    
    log_dir = "timelimit-ui/data/logs"
    log_file = "timelimit-ui/data/logs/timelimit-ui.log"
    
    dir_ok = check_directory_exists(log_dir, "Log directory")
    
    if os.path.exists(log_file):
        print(f"✅ Log file exists: {log_file}")
        try:
            with open(log_file, 'r') as f:
                content = f.read()
                if content:
                    print(f"✅ Log file has content ({len(content)} bytes)")
                    return True
                else:
                    print(f"⚠️ Log file is empty")
                    return False
        except Exception as e:
            print(f"❌ Could not read log file: {e}")
            return False
    else:
        print(f"⚠️ Log file does not exist: {log_file}")
        print(f"   This is expected for first-time setup")
        return True  # Not a failure, just not created yet

def check_web_server_file():
    """Check if web server file has enhanced logging."""
    print("\n=== Checking Web Server Configuration ===")
    
    web_server_path = "timelimit-ui/rootfs/usr/bin/web_server.py"
    
    if not check_file_exists(web_server_path, "Web server file"):
        return False
    
    try:
        with open(web_server_path, 'r') as f:
            content = f.read()
            
        # Check for enhanced logging features
        checks = [
            ("import logging", "Logging import"),
            ("LOG_DIR = \"/data/logs\"", "Log directory constant"),
            ("LOG_FILE = \"/data/logs/timelimit-ui.log\"", "Log file constant"),
            ("os.makedirs(LOG_DIR, exist_ok=True)", "Log directory creation"),
            ("logging.basicConfig(", "Logging configuration"),
            ("FileHandler(LOG_FILE)", "File logging handler"),
            ("Enhanced logging function", "Enhanced logging function")
        ]
        
        all_checks_passed = True
        for check_text, description in checks:
            if check_text in content:
                print(f"✅ {description} found")
            else:
                print(f"❌ {description} NOT found")
                all_checks_passed = False
        
        return all_checks_passed
        
    except Exception as e:
        print(f"❌ Could not read web server file: {e}")
        return False

def check_test_script():
    """Check if test script exists and is executable."""
    print("\n=== Checking Test Script ===")
    
    test_script_path = "timelimit-ui/test_server_connection.py"
    
    if not check_file_exists(test_script_path, "Test script"):
        return False
    
    try:
        with open(test_script_path, 'r') as f:
            content = f.read()
            
        # Check for essential test functions
        checks = [
            ("def test_server_connection", "Server connection test"),
            ("def test_ui_server", "UI server test"),
            ("def test_ui_endpoints", "UI endpoints test"),
            ("def check_log_files", "Log file check"),
            ("if __name__ == \"__main__\":", "Main execution block")
        ]
        
        all_checks_passed = True
        for check_text, description in checks:
            if check_text in content:
                print(f"✅ {description} found")
            else:
                print(f"❌ {description} NOT found")
                all_checks_passed = False
        
        return all_checks_passed
        
    except Exception as e:
        print(f"❌ Could not read test script: {e}")
        return False

def check_documentation():
    """Check if documentation files exist."""
    print("\n=== Checking Documentation ===")
    
    docs = [
        ("timelimit-ui/local-dev-setup.md", "Local development setup guide"),
        ("timelimit-ui/LOCAL_DEVELOPMENT_PLAN.md", "Development plan"),
        ("timelimit-ui/README.md", "README file")
    ]
    
    all_docs_ok = True
    for doc_path, description in docs:
        if os.path.exists(doc_path):
            print(f"✅ {description}: {doc_path}")
        else:
            print(f"❌ {description}: {doc_path} - NOT FOUND")
            all_docs_ok = False
    
    return all_docs_ok

def main():
    """Run all verification tests."""
    print("=== TimeLimit UI Local Development Setup Verification ===")
    
    # Change to the timelimit-ui directory
    os.chdir("timelimit-ui")
    
    # Run all checks
    checks = [
        ("Python Dependencies", check_python_dependencies),
        ("Configuration Files", check_config_file),
        ("Log Directory", check_log_directory),
        ("Web Server Configuration", check_web_server_file),
        ("Test Script", check_test_script),
        ("Documentation", check_documentation)
    ]
    
    results = []
    for check_name, check_function in checks:
        print(f"\n{'='*60}")
        print(f"Running: {check_name}")
        print(f"{'='*60}")
        try:
            result = check_function()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed with error: {e}")
            results.append((check_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! The local development setup is ready.")
        print("\nNext steps:")
        print("1. Run 'python test_server_connection.py' to test server connectivity")
        print("2. Start the web server: 'python rootfs/usr/bin/web_server.py'")
        print("3. Open the dashboard in your browser: http://localhost:8099")
        print("4. Check log files in 'data/logs/timelimit-ui.log'")
        return 0
    else:
        print(f"\n❌ {total - passed} checks failed.")
        print("Please review the failed checks and fix any issues.")
        return 1

if __name__ == "__main__":
