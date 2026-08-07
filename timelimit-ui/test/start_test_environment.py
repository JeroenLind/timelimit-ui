#!/usr/bin/env python3
"""Comprehensive test environment script for TimeLimit UI.

This script starts the webserver and all other components for local testing.
It provides a single entry point to start the complete test environment.
"""

import os
import sys
import subprocess
import time
import threading
import signal
import json
from pathlib import Path

# No longer needed - web_server.py now uses relative paths based on script location
# os.environ['TLUI_ROOTFS_PATH'] = str(Path('../rootfs').resolve())

# Global variables for process management
processes = []
server_process = None
log_file = None

def setup_environment():
    """Set up the test environment directories and files."""
    print("=== Setting up test environment ===")
    
    # Change to the timelimit-ui directory
    os.chdir(Path(__file__).resolve().parent.parent)
    
    # Create necessary directories if they don't exist
    directories = ["data", "data/logs", "rootfs/usr/bin"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"[OK] Ensured directory exists: {directory}")
    
    # Create options.json if it doesn't exist
    options_path = "data/options.json"
    if not os.path.exists(options_path):
        options = {
            "server_url": "http://localhost:8080",
            "logging_mode": "verbose"
        }
        with open(options_path, 'w') as f:
            json.dump(options, f, indent=2)
        print(f"[OK] Created options.json: {options_path}")
    
    # Create log file if it doesn't exist
    log_path = "data/logs/timelimit-ui.log"
    if not os.path.exists(log_path):
        Path(log_path).touch()
        print(f"[OK] Created log file: {log_path}")
    
    print("Environment setup complete.\n")

def start_web_server():
    """Start the TimeLimit UI web server."""
    global server_process
    
    print("=== Starting TimeLimit UI Web Server ===")
    
    # Change to the rootfs/usr/bin directory where web_server.py is located
    working_dir = Path(__file__).resolve().parent.parent / "rootfs"
    server_dir = working_dir / "usr" / "bin"
    server_script = r"usr\bin\web_server.py"
    
    if not os.path.exists(os.path.join(working_dir, server_script)):
        print(f"[ERROR] Web server script not found: {server_script}")
        return False
    
    try:
        # Start the web server
        server_process = subprocess.Popen(
            [sys.executable, server_script],
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Wait for server to start
        print("Waiting for web server to start...")
        time.sleep(5)
        
        # Check if server is running
        if server_process.poll() is not None:
            # Server has terminated
            output = server_process.stdout.read() if server_process.stdout else ""
            print(f"[ERROR] Web server failed to start. Output:\n{output}")
            return False
        
        print(f"[OK] Web server started successfully (PID: {server_process.pid})")
        print(f"   Server is running on http://localhost:8099")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to start web server: {e}")
        return False

def start_frontend_components():
    """Start frontend components (if needed)."""
    print("=== Starting Frontend Components ===")
    
    # In this setup, the frontend is served by the web server
    # The web server serves dashboard.html and JavaScript files
    frontend_dir = "rootfs/usr/bin"
    
    if not os.path.exists(frontend_dir):
        print(f"[ERROR] Frontend directory not found: {frontend_dir}")
        return False
    
    # Check for essential frontend files
    essential_files = [
        "dashboard.html",
        "ui.js",
        "sync.js",
        "state.js",
        "tree.js",
        "wizard.js",
        "style.css"
    ]
    
    missing_files = []
    for file in essential_files:
        if not os.path.exists(os.path.join(frontend_dir, file)):
            missing_files.append(file)
    
    if missing_files:
        print(f"[WARNING] Missing frontend files: {', '.join(missing_files)}")
        print("   This may be expected if frontend is not fully set up yet.")
    else:
        print("[OK] All frontend components are present")
    
    print("Frontend components setup complete.\n")
    return True

def monitor_server_output():
    """Monitor server output for errors."""
    if not server_process or not server_process.stdout:
        return
    
    for line in iter(server_process.stdout.readline, ''):
        if line:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [SERVER] {line.strip()}")
            
            # Write to log file
            log_path = "data/logs/timelimit-ui.log"
            with open(log_path, 'a') as f:
                f.write(f"[{timestamp}] [SERVER] {line}")

def start_server_monitor():
    """Start a thread to monitor server output."""
    monitor_thread = threading.Thread(target=monitor_server_output, daemon=True)
    monitor_thread.start()
    return monitor_thread

def check_server_health():
    """Check if the web server is responding."""
    print("=== Checking Server Health ===")
    
    try:
        import requests
        
        # Test UI server endpoint
        response = requests.get("http://localhost:8099", timeout=5)
        if response.status_code == 200:
            print("[OK] UI server is responding correctly")
            return True
        else:
            print(f"[ERROR] UI server returned status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] UI server health check failed: {e}")
        return False

def run_test_suite():
    """Run the test suite to verify everything is working."""
    print("=== Running Test Suite ===")
    print(f"[DEBUG] Huidige Python interpreter: {sys.executable}")
    
    # Run the existing test_server_connection.py script
    test_script = "test_server_connection.py"
    
    if os.path.exists(test_script):
        try:
            result = subprocess.run(
                [sys.executable, test_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            print("Test script output:")
            print(result.stdout)
            
            if result.stderr:
                print("Test script errors:")
                print(result.stderr)
            
            if result.returncode == 0:
                print("[OK] Test suite completed successfully")
                return True
            else:
                print(f"[ERROR] Test suite failed with return code: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            print("[ERROR] Test suite timed out")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to run test suite: {e}")
            return False
    else:
        print(f"[ERROR] Test script not found: {test_script}")
        return False

def print_startup_info():
    """Print information about the started services."""
    print("\n" + "="*60)
    print("TIME LIMIT UI TEST ENVIRONMENT STARTED")
    print("="*60)
    print("\nServices running:")
    print("  • TimeLimit UI Web Server (http://localhost:8099)")
    print("  • Frontend Dashboard (served by web server)")
    print("  • API Client (for TimeLimit server communication)")
    print("  • Crypto Utilities (for security operations)")
    print("\nAccess the UI in your browser:")
    print("  http://localhost:8099")
    print("\nLog files:")
    print("  • Application logs: timelimit-ui/data/logs/timelimit-ui.log")
    print("  • Server output: displayed above")
    print("\nTo stop all services:")
    print("  • Press Ctrl+C in this terminal")
    print("  • Or run 'pkill -f web_server.py' in another terminal")
    print("="*60)

def cleanup():
    """Clean up and stop all processes."""
    print("\n=== Cleaning up and stopping services ===")
    
    # Stop web server
    if server_process:
        print("Stopping web server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait()
        print("[OK] Web server stopped")
    
    print("[OK] Cleanup complete")

def main():
    """Main function to start the test environment."""
    print("Starting TimeLimit UI Test Environment")
    print("="*60)
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\n[STOP] Received shutdown signal")
        cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Step 1: Set up environment
        setup_environment()
        
        # Step 2: Start web server
        if not start_web_server():
            print("[ERROR] Failed to start web server. Exiting.")
            return 1
        
        # Step 3: Start frontend components
        start_frontend_components()
        
        # Step 4: Start server monitor thread
        monitor_thread = start_server_monitor()
        
        # Step 5: Check server health
        if not check_server_health():
            print("[ERROR] Server health check failed. Continuing anyway...")
        
        # Step 6: Print startup information
        print_startup_info()
        
        # Step 7: Run test suite
        print("\nRunning initial test suite...")
        run_test_suite()
        
        # Step 8: Keep the script running
        print("\nTest environment is running. Press Ctrl+C to stop.")
        
        # Wait for user to interrupt
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
        cleanup()
        return 0
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        cleanup()
        return 1

if __name__ == "__main__":
    sys.exit(main())
