#!/usr/bin/env python3
"""Comprehensive test environment script for TimeLimit UI.

This script starts the webserver and all other components for local testing.
It provides a single entry point to start the complete test environment.

Required System Utilities:
    - Unix/Linux/macOS:
        - lsof: Used to find processes listening on a specific port
          Install with: sudo apt-get install lsof
        - kill: Used to terminate processes by PID
    - Windows:
        - PowerShell with Get-NetTCPConnection (available on Windows 8+)
        - taskkill: Used to terminate processes by PID (built-in to Windows)

Required Python Dependencies:
    - requests: For HTTP health checks
      Install with: pip install requests

Usage:
    python start_test_environment.py              # Exit if instance running
    python start_test_environment.py --kill-existing  # Kill existing instance and restart
"""

import os
import sys
import subprocess
import time
import threading
import signal
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime

# No longer needed - web_server.py now uses relative paths based on script location
# os.environ['TLUI_ROOTFS_PATH'] = str(Path('../rootfs').resolve())

# Global variables for process management
processes = []
server_process = None
log_file = None
TIMESTAMPED_LOG_PATH = None
kill_existing = False

MAX_LOG_FILES = 10

# Server configuration
SERVER_URL = "http://localhost:8099"
SERVER_PORT = 8099


def check_requests_available():
    """Check if the requests library is available.

    Returns:
        bool: True if requests is available, False otherwise.
    """
    try:
        import requests

        return True
    except ImportError:
        return False


def check_existing_instance():
    """Check if a TimeLimit UI instance is already running on port 8099.

    Sends an HTTP GET request to http://localhost:8099/ to verify if
    an instance is already active.

    Returns:
        bool: True if an instance is running (status 200), False otherwise.
    """
    if not check_requests_available():
        print(
            "[WARNING] 'requests' library not available. Cannot check for existing instance."
        )
        print("         Install with: pip install requests")
        return False

    try:
        import requests

        response = requests.get(SERVER_URL, timeout=5)
        if response.status_code == 200:
            return True
        return False
    except requests.exceptions.ConnectionError:
        # Connection refused - no server running
        return False
    except requests.exceptions.Timeout:
        # Server not responding within timeout
        return False
    except requests.exceptions.RequestException as e:
        # Other network errors
        print(f"[WARNING] Error checking for existing instance: {e}")
        return False


def get_pid_on_port(port):
    """Get the PID of the process listening on the specified port.

    Uses lsof on Unix/Linux/macOS and PowerShell Get-NetTCPConnection on Windows.

    Required System Utilities:
        - Unix/Linux/macOS: lsof (install with: sudo apt-get install lsof)
        - Windows: PowerShell with Get-NetTCPConnection (available on Windows 8+)

    Args:
        port: The port number to check.

    Returns:
        int or None: The PID if found, None otherwise.
    """
    try:
        if sys.platform == "win32":
            # Windows: Use PowerShell to get PID on port
            # Get-Process -Id (Get-NetTCPConnection -LocalPort <port>).OwningProcess
            ps_command = (
                f"Get-NetTCPConnection -LocalPort {port} -State Listen | "
                f"Select-Object -ExpandProperty OwningProcess"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Get the first PID
                pids = result.stdout.strip().split("\n")
                return int(pids[0])
            return None
        else:
            # Unix/Linux/macOS: Use lsof
            # lsof -i :<port> -t returns just the PIDs
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Get the first PID (there might be multiple)
                pids = result.stdout.strip().split("\n")
                return int(pids[0])
            return None

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout while checking port {port}")
        return None
    except FileNotFoundError as e:
        if sys.platform == "win32":
            print(f"[ERROR] PowerShell command failed: {e}")
            print("         Ensure PowerShell is available (Windows 8+)")
        else:
            print(f"[ERROR] 'lsof' command not found. Please install lsof.")
            print("         On Ubuntu/Debian: sudo apt-get install lsof")
            print("         On macOS: lsof is usually pre-installed")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get PID on port {port}: {e}")
        return None


def kill_process_by_pid(pid):
    """Kill a process by its PID.

    Uses kill command on Unix/Linux/macOS and taskkill on Windows.

    Args:
        pid: The process ID to kill.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Detect OS and use appropriate kill command
        if sys.platform == "win32":
            # Windows: use taskkill
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        else:
            # Unix/Linux/macOS: use kill
            result = subprocess.run(
                ["kill", "-9", str(pid)], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout while killing process {pid}")
        return False
    except FileNotFoundError:
        print(f"[ERROR] Kill command not found")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to kill process {pid}: {e}")
        return False


def terminate_existing_instance():
    """Terminate the existing TimeLimit UI instance.

    Finds and kills the process listening on port 8099.

    Returns:
        bool: True if termination was successful or no instance was running,
              False if termination failed.
    """
    print(f"=== Checking for existing instance on port {SERVER_PORT} ===")

    pid = get_pid_on_port(SERVER_PORT)

    if pid is None:
        print("[OK] No existing instance found on port 8099")
        return True

    print(f"[INFO] Found process {pid} listening on port {SERVER_PORT}")
    print(f"[INFO] Terminating process {pid}...")

    if kill_process_by_pid(pid):
        print(f"[OK] Successfully terminated process {pid}")
        # Wait a moment for the port to be released
        time.sleep(2)
        return True
    else:
        print(f"[ERROR] Failed to terminate process {pid}")
        return False


def rotate_log_files():
    """Remove oldest log files if there are more than MAX_LOG_FILES."""
    log_dir = Path("data/logs")
    if not log_dir.exists():
        return

    # Find all log files matching the pattern YYYY-MM-DD_HH-MM-SS_*.log
    log_pattern = str(log_dir / "*_*.log")
    log_files = sorted(glob.glob(log_pattern), key=os.path.getmtime)

    # Remove oldest files if we have more than MAX_LOG_FILES
    while len(log_files) > MAX_LOG_FILES:
        oldest_file = log_files.pop(0)
        try:
            os.remove(oldest_file)
            print(f"[OK] Removed old log file: {oldest_file}")
        except Exception as e:
            print(f"[WARNING] Could not remove old log file {oldest_file}: {e}")


def create_timestamped_log_file():
    """Create a new log file with timestamp in the filename."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"{timestamp}_timelimit-ui.log"
    log_path = Path("data/logs") / log_filename

    # Ensure directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the file
    log_path.touch()

    return str(log_path)


def setup_environment():
    """Set up the test environment directories and files."""
    global TIMESTAMPED_LOG_PATH

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
        options = {"server_url": "http://localhost:8080", "logging_mode": "verbose"}
        with open(options_path, "w") as f:
            json.dump(options, f, indent=2)
        print(f"[OK] Created options.json: {options_path}")

    # Rotate old log files
    rotate_log_files()

    # Create timestamped log file
    TIMESTAMPED_LOG_PATH = create_timestamped_log_file()
    print(f"[OK] Created timestamped log file: {TIMESTAMPED_LOG_PATH}")

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
            bufsize=1,
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
        "style.css",
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
    global TIMESTAMPED_LOG_PATH

    if not server_process or not server_process.stdout:
        return

    for line in iter(server_process.stdout.readline, ""):
        if line:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [SERVER] {line.strip()}")

            # Write to timestamped log file
            log_path = TIMESTAMPED_LOG_PATH or "data/logs/timelimit-ui.log"
            with open(log_path, "a") as f:
                f.write(f"[{timestamp}] [SERVER] {line}")


def start_server_monitor():
    """Start a thread to monitor server output."""
    monitor_thread = threading.Thread(target=monitor_server_output, daemon=True)
    monitor_thread.start()
    return monitor_thread


def check_server_health():
    """Check if the web server is responding."""
    print("=== Checking Server Health ===")

    if not check_requests_available():
        print("[WARNING] 'requests' library not available. Skipping health check.")
        print("         Install with: pip install requests")
        return False

    try:
        import requests

        # Test UI server endpoint
        response = requests.get(SERVER_URL, timeout=5)
        if response.status_code == 200:
            print("[OK] UI server is responding correctly")
            return True
        else:
            print(f"[ERROR] UI server returned status code: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] UI server health check failed - Connection refused: {e}")
        return False
    except requests.exceptions.Timeout:
        print(f"[ERROR] UI server health check failed - Request timed out")
        return False
    except requests.exceptions.RequestException as e:
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
                timeout=30,
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
                print(
                    f"[ERROR] Test suite failed with return code: {result.returncode}"
                )
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
    global TIMESTAMPED_LOG_PATH

    print("\n" + "=" * 60)
    print("TIME LIMIT UI TEST ENVIRONMENT STARTED")
    print("=" * 60)
    print("\nServices running:")
    print("  • TimeLimit UI Web Server (http://localhost:8099)")
    print("  • Frontend Dashboard (served by web server)")
    print("  • API Client (for TimeLimit server communication)")
    print("  • Crypto Utilities (for security operations)")
    print("\nAccess the UI in your browser:")
    print("  http://localhost:8099")
    print("\nLog files:")
    log_path = TIMESTAMPED_LOG_PATH or "data/logs/timelimit-ui.log"
    print(f"  • Application logs: {log_path}")
    print("  • Server output: displayed above")
    print("\nTo stop all services:")
    print("  • Press Ctrl+C in this terminal")
    print("  • Or run 'pkill -f web_server.py' in another terminal")
    print("=" * 60)


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


def parse_arguments():
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Start the TimeLimit UI test environment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python start_test_environment.py              # Exit if instance running
    python start_test_environment.py --kill-existing  # Kill existing instance and restart
        """,
    )

    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill any existing instance on port 8099 before starting",
    )

    return parser.parse_args()


def main():
    """Main function to start the test environment."""
    global kill_existing

    # Parse command-line arguments
    args = parse_arguments()
    kill_existing = args.kill_existing

    print("Starting TimeLimit UI Test Environment")
    print("=" * 60)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\n[STOP] Received shutdown signal")
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Step 1: Check for existing instance
        if check_existing_instance():
            if kill_existing:
                print(
                    f"[WARNING] An existing instance is running on port {SERVER_PORT}"
                )
                if not terminate_existing_instance():
                    print("[ERROR] Failed to terminate existing instance. Exiting.")
                    return 1
            else:
                print(
                    f"[ERROR] An existing TimeLimit UI instance is already running on {SERVER_URL}"
                )
                print(
                    "         Use --kill-existing flag to terminate it automatically."
                )
                print("         Or manually stop it with: pkill -f web_server.py")
                return 1

        # Step 2: Set up environment
        setup_environment()

        # Step 3: Start web server
        if not start_web_server():
            print("[ERROR] Failed to start web server. Exiting.")
            return 1

        # Step 4: Start frontend components
        start_frontend_components()

        # Step 5: Start server monitor thread
        monitor_thread = start_server_monitor()

        # Step 6: Check server health
        if not check_server_health():
            print("[ERROR] Server health check failed. Continuing anyway...")

        # Step 7: Print startup information
        print_startup_info()

        # Step 8: Run test suite
        print("\nRunning initial test suite...")
        run_test_suite()

        # Step 9: Keep the script running
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
