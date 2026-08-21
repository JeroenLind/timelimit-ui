#!/usr/bin/env python
"""Script to run tests and save output to file."""
import sys
import os

# Change to the dashboardV2 directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add the current directory to the path
sys.path.insert(0, os.getcwd())

import pytest

# Run tests and save output
exit_code = pytest.main([
    '-v',
    '--tb=short',
    'tests/test_create_family.py',
    'tests/test_create_family_integration.py',
    'tests/test_landing.py',
    'tests/test_config.py',
    'tests/test_scheduler.py',
    'tests/test_sync_manager.py',
    'tests/test_auth_client_logging.py'
])

sys.exit(exit_code)