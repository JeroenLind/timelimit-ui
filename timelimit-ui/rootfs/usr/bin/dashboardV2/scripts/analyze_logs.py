#!/usr/bin/env python3
"""Log analysis script for TimeLimit dashboardV2.

This script parses log files for errors, security events, communication issues,
and other operational data. It supports both JSON structured logs and plain text
logs with flexible filtering and output options.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log level constants
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Standard JSON log fields
STANDARD_FIELDS = {"timestamp", "level", "logger", "event", "request_id", "component"}

# Contextual fields that may appear in logs
CONTEXTUAL_FIELDS = {
    "server_url",
    "error_code",
    "duration_ms",
    "message",
    "exception",
    "traceback",
    "client_ip",
    "method",
    "path",
    "status_code",
    "user_agent",
    "session_id",
    "user_id",
    "device_id",
    "category",
    "action",
    "data",
}


class LogAnalyzer:
    """Analyzes log files for various patterns and events."""

    def __init__(
        self,
        log_file: Optional[str] = None,
        log_dir: Optional[str] = None,
        log_level_filter: Optional[str] = None,
        request_id_filter: Optional[str] = None,
    ):
        """Initialize the log analyzer.

        Args:
            log_file: Path to a single log file.
            log_dir: Path to a directory of log files.
            log_level_filter: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            request_id_filter: Filter by request ID for tracing.
        """
        self.log_file = Path(log_file) if log_file else None
        self.log_dir = Path(log_dir) if log_dir else None
        self.log_level_filter = log_level_filter.upper() if log_level_filter else None
        self.request_id_filter = request_id_filter

        # Analysis categories
        self.errors: List[Dict[str, Any]] = []
        self.security_events: List[Dict[str, Any]] = []
        self.communication_issues: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info_events: List[Dict[str, Any]] = []
        self.scheduler_events: List[Dict[str, Any]] = []
        self.debug_events: List[Dict[str, Any]] = []

        # Track all entries for request ID filtering
        self.all_entries: List[Dict[str, Any]] = []

    def analyze(self) -> Dict[str, Any]:
        """Analyze the log file(s).

        Returns:
            Dictionary with analysis results.
        """
        log_files = self._get_log_files()

        if not log_files:
            return {"error": "No log files found"}

        for log_path in log_files:
            self._analyze_file(log_path)

        # Apply request ID filter if specified
        if self.request_id_filter:
            self._filter_by_request_id()

        return self._build_results()

    def _get_log_files(self) -> List[Path]:
        """Get list of log files to analyze.

        Returns:
            List of log file paths.
        """
        log_files = []

        if self.log_file and self.log_file.exists():
            log_files.append(self.log_file)
        elif self.log_dir and self.log_dir.exists():
            # Find all .log files in directory
            log_files.extend(sorted(self.log_dir.glob("*.log")))
            # Also include files without extension if they exist
            log_files.extend(sorted(self.log_dir.glob("*.log.*")))
        else:
            logger.error("Log file or directory not found")
            return []

        return log_files

    def _analyze_file(self, log_path: Path) -> None:
        """Analyze a single log file.

        Args:
            log_path: Path to the log file.
        """
        logger.info(f"Analyzing log file: {log_path}")

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    self._parse_line(line.strip())
        except Exception as e:
            logger.error(f"Error reading log file {log_path}: {e}")

    def _parse_line(self, line: str) -> None:
        """Parse a single log line.

        Args:
            line: The log line to parse.
        """
        if not line:
            return

        try:
            # Try to parse as JSON (structlog format)
            data = json.loads(line)
            self._process_json_log(data)
        except json.JSONDecodeError:
            # Try to parse as plain text
            self._process_text_log(line)

    def _process_json_log(self, data: Dict[str, Any]) -> None:
        """Process a JSON log entry.

        Args:
            data: The parsed JSON log entry.
        """
        level = data.get("level", "").upper()
        event = data.get("event", "")
        request_id = data.get("request_id", "")

        # Apply log level filter
        if self.log_level_filter and level != self.log_level_filter:
            return

        # Store entry for request ID filtering
        self.all_entries.append(data)

        # Categorize by level
        if level in ("ERROR", "CRITICAL"):
            self.errors.append(data)
        elif level == "WARNING":
            self.warnings.append(data)
        elif level == "INFO":
            self.info_events.append(data)
        elif level == "DEBUG":
            self.debug_events.append(data)

        # Check for security events
        if self._is_security_event(event, data):
            self.security_events.append(data)

        # Check for communication issues
        if self._is_communication_issue(event, data):
            self.communication_issues.append(data)

        # Check for scheduler events
        if self._is_scheduler_event(event, data):
            self.scheduler_events.append(data)

    def _process_text_log(self, line: str) -> None:
        """Process a plain text log line.

        Args:
            line: The log line to process.
        """
        # Extract level from text
        level = self._extract_level_from_text(line)

        # Apply log level filter
        if self.log_level_filter and level != self.log_level_filter:
            return

        entry = {"line": line, "level": level}
        self.all_entries.append(entry)

        # Categorize by level
        if level in ("ERROR", "CRITICAL"):
            self.errors.append(entry)
        elif level == "WARNING":
            self.warnings.append(entry)
        elif level == "INFO":
            self.info_events.append(entry)
        elif level == "DEBUG":
            self.debug_events.append(entry)

        # Check for security patterns
        if self._is_security_text(line):
            self.security_events.append(entry)

        # Check for communication patterns
        if self._is_communication_text(line):
            self.communication_issues.append(entry)

        # Check for scheduler patterns
        if self._is_scheduler_text(line):
            self.scheduler_events.append(entry)

    def _extract_level_from_text(self, line: str) -> str:
        """Extract log level from text line.

        Args:
            line: The log line.

        Returns:
            Extracted log level or "INFO" as default.
        """
        level_patterns = [
            (r"\bCRITICAL\b", "CRITICAL"),
            (r"\bERROR\b", "ERROR"),
            (r"\bWARNING\b", "WARNING"),
            (r"\bINFO\b", "INFO"),
            (r"\bDEBUG\b", "DEBUG"),
        ]

        for pattern, level in level_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return level

        return "INFO"

    def _is_security_event(self, event: str, data: Dict[str, Any]) -> bool:
        """Check if the log entry is a security event.

        Args:
            event: The event name.
            data: The log entry data.

        Returns:
            True if this is a security event.
        """
        security_keywords = [
            "auth",
            "token",
            "login",
            "password",
            "verify",
            "invalid",
            "unauthorized",
            "session",
            "credential",
            "authentication",
            "sign-in",
            "sign_out",
        ]

        event_lower = event.lower()
        message = data.get("message", "").lower()
        logger_name = data.get("logger", "").lower()

        for keyword in security_keywords:
            if keyword in event_lower or keyword in message or keyword in logger_name:
                return True

        return False

    def _is_communication_issue(self, event: str, data: Dict[str, Any]) -> bool:
        """Check if the log entry is a communication issue.

        Args:
            event: The event name.
            data: The log entry data.

        Returns:
            True if this is a communication issue.
        """
        comm_keywords = [
            "timeout",
            "connection refused",
            "connection_refused",
            "connection reset",
            "connection_reset",
            "network error",
            "network_error",
            "failed to connect",
            "unreachable",
            "dns",
            "ssl",
            "tls",
            "certificate",
            "handshake",
            "socket",
            "socket error",
            "socket_error",
            "connection error",
            "connection_error",
            "request failed",
            "request_failed",
        ]

        event_lower = event.lower()
        message = data.get("message", "").lower()
        exception = str(data.get("exception", "")).lower()

        for keyword in comm_keywords:
            if keyword in event_lower or keyword in message or keyword in exception:
                return True

        return False

    def _is_scheduler_event(self, event: str, data: Dict[str, Any]) -> bool:
        """Check if the log entry is a scheduler event.

        Args:
            event: The event name.
            data: The log entry data.

        Returns:
            True if this is a scheduler event.
        """
        scheduler_keywords = [
            "server check",
            "server_check",
            "scheduler",
            "timechecker",
            "scheduled",
            "cron",
            "job",
            "task",
            "check server",
            "check_server",
            "health check",
            "health_check",
        ]

        event_lower = event.lower()
        message = data.get("message", "").lower()
        logger_name = data.get("logger", "").lower()

        for keyword in scheduler_keywords:
            if keyword in event_lower or keyword in message or keyword in logger_name:
                return True

        return False

    def _is_security_text(self, line: str) -> bool:
        """Check if text log line is a security event.

        Args:
            line: The log line.

        Returns:
            True if this is a security event.
        """
        security_patterns = [
            r"\bauth\b",
            r"\btoken\b",
            r"\bpassword\b",
            r"\bverify\b",
            r"\bunauthorized\b",
            r"\binvalid.*token\b",
            r"\bcredential\b",
            r"\bauthentication\b",
            r"\bsign[-_]?in\b",
            r"\bsign[-_]?out\b",
            r"\bsession\b",
        ]

        line_lower = line.lower()
        for pattern in security_patterns:
            if re.search(pattern, line_lower):
                return True

        return False

    def _is_communication_text(self, line: str) -> bool:
        """Check if text log line is a communication issue.

        Args:
            line: The log line.

        Returns:
            True if this is a communication issue.
        """
        comm_patterns = [
            r"\btimeout\b",
            r"\bconnection.*refused\b",
            r"\bconnection.*reset\b",
            r"\bnetwork.*error\b",
            r"\bfailed.*connect\b",
            r"\bunreachable\b",
            r"\bdns.*error\b",
            r"\bssl.*error\b",
            r"\btls.*error\b",
            r"\bcertificate.*error\b",
            r"\bhandshake.*fail\b",
            r"\bsocket.*error\b",
            r"\brequest.*fail\b",
        ]

        line_lower = line.lower()
        for pattern in comm_patterns:
            if re.search(pattern, line_lower):
                return True

        return False

    def _is_scheduler_text(self, line: str) -> bool:
        """Check if text log line is a scheduler event.

        Args:
            line: The log line.

        Returns:
            True if this is a scheduler event.
        """
        scheduler_patterns = [
            r"\bserver check\b",
            r"\bserver_check\b",
            r"\bscheduler\b",
            r"\btimechecker\b",
            r"\bscheduled\b",
            r"\bcron\b",
            r"\bjob\b",
            r"\bcheck server\b",
            r"\bcheck_server\b",
            r"\bhealth check\b",
            r"\bhealth_check\b",
        ]

        line_lower = line.lower()
        for pattern in scheduler_patterns:
            if re.search(pattern, line_lower):
                return True

        return False

    def _filter_by_request_id(self) -> None:
        """Filter all categories by request ID."""
        self.errors = [e for e in self.errors if self._has_request_id(e)]
        self.security_events = [e for e in self.security_events if self._has_request_id(e)]
        self.communication_issues = [e for e in self.communication_issues if self._has_request_id(e)]
        self.warnings = [e for e in self.warnings if self._has_request_id(e)]
        self.info_events = [e for e in self.info_events if self._has_request_id(e)]
        self.scheduler_events = [e for e in self.scheduler_events if self._has_request_id(e)]
        self.debug_events = [e for e in self.debug_events if self._has_request_id(e)]

    def _has_request_id(self, entry: Dict[str, Any]) -> bool:
        """Check if entry has the filtered request ID.

        Args:
            entry: The log entry.

        Returns:
            True if entry has the request ID filter.
        """
        entry_request_id = entry.get("request_id", "")
        if isinstance(entry_request_id, str):
            return self.request_id_filter in entry_request_id
        return False

    def _build_results(self) -> Dict[str, Any]:
        """Build the results dictionary.

        Returns:
            Dictionary with analysis results.
        """
        return {
            "summary": {
                "total_errors": len(self.errors),
                "total_security_events": len(self.security_events),
                "total_communication_issues": len(self.communication_issues),
                "total_warnings": len(self.warnings),
                "total_info_events": len(self.info_events),
                "total_scheduler_events": len(self.scheduler_events),
                "total_debug_events": len(self.debug_events),
                "total_entries": len(self.all_entries),
                "log_level_filter": self.log_level_filter,
                "request_id_filter": self.request_id_filter,
            },
            "errors": self.errors,
            "security_events": self.security_events,
            "communication_issues": self.communication_issues,
            "warnings": self.warnings,
            "info_events": self.info_events[:100],  # Limit to first 100
            "scheduler_events": self.scheduler_events,
            "debug_events": self.debug_events,
        }


def print_report(results: Dict[str, Any]) -> str:
    """Print a formatted report.

    Args:
        results: The analysis results.

    Returns:
        The formatted report as a string.
    """
    lines = []
    
    if "error" in results:
        lines.append(f"Error: {results['error']}")
        output = "\n".join(lines)
        print(output)
        return output

    summary = results.get("summary", {})

    lines.append("\n" + "=" * 60)
    lines.append("LOG ANALYSIS REPORT")
    lines.append("=" * 60)

    # Summary section
    lines.append("\nSUMMARY:")
    lines.append(f"  Total Errors: {summary.get('total_errors', 0)}")
    lines.append(f"  Total Security Events: {summary.get('total_security_events', 0)}")
    lines.append(f"  Total Communication Issues: {summary.get('total_communication_issues', 0)}")
    lines.append(f"  Total Warnings: {summary.get('total_warnings', 0)}")
    lines.append(f"  Total Info Events: {summary.get('total_info_events', 0)}")
    lines.append(f"  Total Scheduler Events: {summary.get('total_scheduler_events', 0)}")
    lines.append(f"  Total Debug Events: {summary.get('total_debug_events', 0)}")
    lines.append(f"  Total Entries: {summary.get('total_entries', 0)}")

    if summary.get("log_level_filter"):
        lines.append(f"  Log Level Filter: {summary['log_level_filter']}")
    if summary.get("request_id_filter"):
        lines.append(f"  Request ID Filter: {summary['request_id_filter']}")

    # Detailed sections
    if results.get("errors"):
        lines.append("\nERRORS:")
        for error in results["errors"][:10]:  # Show first 10
            if isinstance(error, dict) and "event" in error:
                lines.append(f"  - [{error.get('level', 'ERROR')}] {error.get('event', 'Unknown')}: {error.get('message', '')}")
            else:
                lines.append(f"  - {error.get('line', '')[:100]}")

    if results.get("security_events"):
        lines.append("\nSECURITY EVENTS:")
        for event in results["security_events"][:10]:
            if isinstance(event, dict) and "event" in event:
                lines.append(f"  - [{event.get('level', 'INFO')}] {event.get('event', 'Unknown')}: {event.get('message', '')}")
            else:
                lines.append(f"  - {event.get('line', '')[:100]}")

    if results.get("communication_issues"):
        lines.append("\nCOMMUNICATION ISSUES:")
        for issue in results["communication_issues"][:10]:
            if isinstance(issue, dict) and "event" in issue:
                lines.append(f"  - [{issue.get('level', 'ERROR')}] {issue.get('event', 'Unknown')}: {issue.get('message', '')}")
            else:
                lines.append(f"  - {issue.get('line', '')[:100]}")

    if results.get("warnings"):
        lines.append("\nWARNINGS:")
        for warning in results["warnings"][:10]:
            if isinstance(warning, dict) and "event" in warning:
                lines.append(f"  - [{warning.get('level', 'WARNING')}] {warning.get('event', 'Unknown')}: {warning.get('message', '')}")
            else:
                lines.append(f"  - {warning.get('line', '')[:100]}")

    if results.get("scheduler_events"):
        lines.append("\nSCHEDULER EVENTS:")
        for event in results["scheduler_events"][:10]:
            if isinstance(event, dict) and "event" in event:
                lines.append(f"  - [{event.get('level', 'INFO')}] {event.get('event', 'Unknown')}: {event.get('message', '')}")
            else:
                lines.append(f"  - {event.get('line', '')[:100]}")

    lines.append("\n" + "=" * 60)
    
    output = "\n".join(lines)
    print(output)
    return output


def analyze_logs(
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    log_level_filter: Optional[str] = None,
    request_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze log files and return results.

    Args:
        log_file: Path to a single log file.
        log_dir: Path to a directory of log files.
        log_level_filter: Filter by log level.
        request_id_filter: Filter by request ID.

    Returns:
        Dictionary with analysis results.
    """
    analyzer = LogAnalyzer(
        log_file=log_file,
        log_dir=log_dir,
        log_level_filter=log_level_filter,
        request_id_filter=request_id_filter,
    )
    return analyzer.analyze()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for errors found).
    """
    parser = argparse.ArgumentParser(
        description="Analyze TimeLimit dashboardV2 logs"
    )

    # Log file options
    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--log-file", "-f",
        type=str,
        help="Path to a single log file",
    )
    file_group.add_argument(
        "--log-dir", "-d",
        type=str,
        help="Path to a directory of log files",
    )

    # Output format
    parser.add_argument(
        "--output", "-o",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # Log level filter
    parser.add_argument(
        "--filter", "--level",
        type=str,
        choices=LOG_LEVELS,
        help="Filter by log level",
    )

    # Request ID filter
    parser.add_argument(
        "--request-id", "-r",
        type=str,
        help="Filter by request ID for tracing",
    )

    args = parser.parse_args()

    analyzer = LogAnalyzer(
        log_file=args.log_file,
        log_dir=args.log_dir,
        log_level_filter=args.filter,
        request_id_filter=args.request_id,
    )
    results = analyzer.analyze()

    if args.output == "json":
        print(json.dumps(results, indent=2, default=str))
    else:
        print_report(results)

    # Return exit code based on errors found
    if results.get("summary", {}).get("total_errors", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())