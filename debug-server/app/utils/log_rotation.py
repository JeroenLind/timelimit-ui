"""Log file rotation and retention management.

This module provides functionality for:
- Generating timestamped log filenames
- Rotating log files on server startup
- Enforcing retention policy (keeping only the N most recent log files)
- Handling file naming conflicts
"""

import glob
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# Default maximum number of log files to retain
DEFAULT_MAX_LOG_FILES = 10

# Log filename pattern: debug-server-YYYY-MM-DD_HH-MM-SS.log
LOG_FILENAME_PATTERN = "debug-server-*.log"


def generate_timestamped_filename(base_name: str = "debug-server") -> str:
    """Generate a timestamped log filename with unique identifier.
    
    Creates a filename in the format: {base_name}-YYYY-MM-DD_HH-MM-SS.log
    
    Args:
        base_name: The base name for the log file (default: "debug-server")
        
    Returns:
        A timestamped log filename string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{base_name}-{timestamp}.log"


def generate_unique_log_path(log_dir: str, base_name: str = "debug-server") -> str:
    """Generate a unique log file path with timestamp and unique identifier.
    
    Creates a path like: {log_dir}/{base_name}-YYYY-MM-DD_HH-MM-SS-{unique_id}.log
    
    This handles potential naming conflicts by appending a unique identifier
    if a file with the same timestamp already exists.
    
    Args:
        log_dir: Directory where the log file should be created
        base_name: The base name for the log file (default: "debug-server")
        
    Returns:
        A unique log file path string
    """
    # Ensure log directory exists
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Generate base timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Try without unique ID first (most common case)
    filename = f"{base_name}-{timestamp}.log"
    full_path = log_path / filename
    
    if not full_path.exists():
        return str(full_path)
    
    # If file exists, append unique identifier
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{base_name}-{timestamp}-{unique_id}.log"
    full_path = log_path / filename
    
    return str(full_path)


def get_log_files(log_dir: str, pattern: str = LOG_FILENAME_PATTERN) -> List[str]:
    """Get all log files in the directory matching the pattern.
    
    Returns files sorted by modification time (oldest first).
    
    Args:
        log_dir: Directory to search for log files
        pattern: Glob pattern to match log files
        
    Returns:
        List of log file paths sorted by modification time (oldest first)
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return []
    
    # Find all matching log files
    pattern_path = str(log_path / pattern)
    log_files = glob.glob(pattern_path)
    
    # Sort by modification time (oldest first)
    log_files.sort(key=os.path.getmtime)
    
    return log_files


def rotate_log_files(
    log_dir: str,
    max_files: int = DEFAULT_MAX_LOG_FILES,
    pattern: str = LOG_FILENAME_PATTERN
) -> List[str]:
    """Rotate log files by removing old files when count exceeds max_files.
    
    This function:
    1. Finds all log files matching the pattern
    2. Sorts them by modification time (oldest first)
    3. Removes the oldest files if count exceeds max_files
    4. Returns list of removed files
    
    Args:
        log_dir: Directory containing log files
        max_files: Maximum number of log files to keep (default: 10)
        pattern: Glob pattern to match log files
        
    Returns:
        List of paths to removed log files
    """
    log_files = get_log_files(log_dir, pattern)
    removed_files = []
    
    # Remove oldest files if we have more than max_files
    while len(log_files) > max_files:
        oldest_file = log_files.pop(0)
        try:
            os.remove(oldest_file)
            removed_files.append(oldest_file)
        except OSError as e:
            # Log error but continue with remaining files
            print(f"[WARNING] Could not remove old log file {oldest_file}: {e}")
    
    return removed_files


def cleanup_old_logs(
    log_dir: str,
    max_files: int = DEFAULT_MAX_LOG_FILES,
    pattern: str = LOG_FILENAME_PATTERN
) -> dict:
    """Clean up old log files and return statistics.
    
    This is a convenience function that combines rotation with statistics.
    
    Args:
        log_dir: Directory containing log files
        max_files: Maximum number of log files to keep (default: 10)
        pattern: Glob pattern to match log files
        
    Returns:
        Dictionary with cleanup statistics:
        - total_files_before: Number of files before cleanup
        - total_files_after: Number of files after cleanup
        - files_removed: Number of files removed
        - removed_files: List of paths to removed files
    """
    log_files = get_log_files(log_dir, pattern)
    total_before = len(log_files)
    
    removed_files = rotate_log_files(log_dir, max_files, pattern)
    
    remaining_files = get_log_files(log_dir, pattern)
    total_after = len(remaining_files)
    
    return {
        "total_files_before": total_before,
        "total_files_after": total_after,
        "files_removed": len(removed_files),
        "removed_files": removed_files,
    }


def get_log_files_info(log_dir: str, pattern: str = LOG_FILENAME_PATTERN) -> List[dict]:
    """Get detailed information about log files.
    
    Returns information about each log file including:
    - Path
    - Size in bytes
    - Modification time
    - Creation time
    
    Args:
        log_dir: Directory containing log files
        pattern: Glob pattern to match log files
        
    Returns:
        List of dictionaries with file information, sorted by modification time (newest first)
    """
    log_files = get_log_files(log_dir, pattern)
    files_info = []
    
    for file_path in log_files:
        try:
            stat = os.stat(file_path)
            files_info.append({
                "path": file_path,
                "size_bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "ctime": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
        except OSError:
            # Skip files that can't be accessed
            continue
    
    # Sort by modification time (newest first)
    files_info.sort(key=lambda x: x["mtime"], reverse=True)
    
    return files_info


def ensure_log_directory(log_dir: str) -> str:
    """Ensure the log directory exists and return its absolute path.
    
    Args:
        log_dir: Directory path to ensure exists
        
    Returns:
        Absolute path to the log directory
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    return str(log_path.absolute())