#!/usr/bin/env python3
"""Log analysis script for TimeLimit debug server.

This script parses log files for errors, security events, and communication issues.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LogAnalyzer:
    """Analyzes log files for various patterns and events."""
    
    def __init__(self, log_file: str):
        """Initialize the log analyzer.
        
        Args:
            log_file: Path to the log file.
        """
        self.log_file = Path(log_file)
        self.errors = []
        self.security_events = []
        self.communication_issues = []
        self.warnings = []
        self.info_events = []
    
    def analyze(self) -> Dict[str, Any]:
        """Analyze the log file.
        
        Returns:
            Dictionary with analysis results.
        """
        if not self.log_file.exists():
            logger.error(f"Log file not found: {self.log_file}")
            return {"error": "Log file not found"}
        
        with open(self.log_file, "r") as f:
            for line in f:
                self._parse_line(line.strip())
        
        return {
            "summary": {
                "total_errors": len(self.errors),
                "total_security_events": len(self.security_events),
                "total_communication_issues": len(self.communication_issues),
                "total_warnings": len(self.warnings),
                "total_info_events": len(self.info_events),
            },
            "errors": self.errors,
            "security_events": self.security_events,
            "communication_issues": self.communication_issues,
            "warnings": self.warnings,
            "info_events": self.info_events[:100],  # Limit to first 100
        }
    
    def _parse_line(self, line: str) -> None:
        """Parse a single log line.
        
        Args:
            line: The log line to parse.
        """
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
        
        if level == "ERROR":
            self.errors.append(data)
        elif level == "WARNING":
            self.warnings.append(data)
        elif level == "INFO":
            self.info_events.append(data)
        
        # Check for security events
        if any(keyword in event.lower() for keyword in [
            "auth", "token", "login", "password", "verify", "invalid", "unauthorized"
        ]):
            self.security_events.append(data)
        
        # Check for communication issues
        if any(keyword in event.lower() for keyword in [
            "timeout", "connection", "refused", "error", "failed", "exception"
        ]):
            self.communication_issues.append(data)
    
    def _process_text_log(self, line: str) -> None:
        """Process a plain text log line.
        
        Args:
            line: The log line to process.
        """
        # Check for error patterns
        error_patterns = [
            r"ERROR",
            r"Exception",
            r"Traceback",
            r"Failed",
            r"Invalid",
            r"Unauthorized",
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.errors.append({"line": line, "pattern": pattern})
                break
        
        # Check for warning patterns
        if "WARNING" in line:
            self.warnings.append({"line": line})
        
        # Check for security patterns
        security_patterns = [
            r"auth",
            r"token",
            r"password",
            r"verify",
            r"invalid.*token",
            r"unauthorized",
        ]
        
        for pattern in security_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.security_events.append({"line": line, "pattern": pattern})
                break
        
        # Check for communication patterns
        comm_patterns = [
            r"timeout",
            r"connection.*refused",
            r"failed.*connect",
            r"network.*error",
        ]
        
        for pattern in comm_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.communication_issues.append({"line": line, "pattern": pattern})
                break


def print_report(results: Dict[str, Any]) -> None:
    """Print a formatted report.
    
    Args:
        results: The analysis results.
    """
    if "error" in results:
        print(f"Error: {results['error']}")
        return
    
    summary = results.get("summary", {})
    
    print("\n" + "=" * 60)
    print("LOG ANALYSIS REPORT")
    print("=" * 60)
    
    print("\nSUMMARY:")
    print(f"  Total Errors: {summary.get('total_errors', 0)}")
    print(f"  Total Security Events: {summary.get('total_security_events', 0)}")
    print(f"  Total Communication Issues: {summary.get('total_communication_issues', 0)}")
    print(f"  Total Warnings: {summary.get('total_warnings', 0)}")
    print(f"  Total Info Events: {summary.get('total_info_events', 0)}")
    
    if results.get("errors"):
        print("\nERRORS:")
        for error in results["errors"][:10]:  # Show first 10
            if isinstance(error, dict) and "event" in error:
                print(f"  - {error.get('event', 'Unknown')}: {error.get('message', '')}")
            else:
                print(f"  - {error.get('line', '')[:100]}")
    
    if results.get("security_events"):
        print("\nSECURITY EVENTS:")
        for event in results["security_events"][:10]:
            if isinstance(event, dict) and "event" in event:
                print(f"  - {event.get('event', 'Unknown')}: {event.get('message', '')}")
            else:
                print(f"  - {event.get('line', '')[:100]}")
    
    if results.get("communication_issues"):
        print("\nCOMMUNICATION ISSUES:")
        for issue in results["communication_issues"][:10]:
            if isinstance(issue, dict) and "event" in issue:
                print(f"  - {issue.get('event', 'Unknown')}: {issue.get('message', '')}")
            else:
                print(f"  - {issue.get('line', '')[:100]}")
    
    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze TimeLimit debug server logs"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="logs/debug-server.log",
        help="Path to the log file (default: logs/debug-server.log)",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(args.log_file)
    results = analyzer.analyze()
    
    if args.output == "json":
        print(json.dumps(results, indent=2))
    else:
        print_report(results)
    
    # Return exit code based on errors found
    if results.get("summary", {}).get("total_errors", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())