"""Scripts package for dashboardV2.

This package contains utility scripts for log analysis and other operational tasks.
"""

from .analyze_logs import LogAnalyzer, analyze_logs, print_report

__all__ = ["LogAnalyzer", "analyze_logs", "print_report"]