#!/usr/bin/env python3
"""Test script for TimeLimit UI server connection testing."""

import requests
import json
import time
import sys
import os

def test_server_connection(server_url="http://localhost:8080"):
    """Test connection to TimeLimit server"""
    print(f"Testing connection to {server_url}")
    
