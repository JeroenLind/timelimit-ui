"""Unit tests for log analysis script.

Tests for LogAnalyzer class, analyze_logs function, print_report function,
JSON/text log parsing, error category detection, security event detection,
communication issue detection, and request ID filtering.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.analyze_logs import (
    LogAnalyzer,
    analyze_logs,
    print_report,
)


class TestLogAnalyzerInitialization:
    """Tests for LogAnalyzer initialization."""

    def test_init_with_log_file(self):
        """Verify LogAnalyzer initializes with log file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            analyzer = LogAnalyzer(log_file=log_file)
            assert str(analyzer.log_file) == log_file

    def test_init_with_log_dir(self):
        """Verify LogAnalyzer initializes with log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(os.path.join(tmpdir, 'test.log')).touch()

            analyzer = LogAnalyzer(log_dir=tmpdir)
            assert str(analyzer.log_dir) == tmpdir

    def test_init_default_values(self):
        """Verify LogAnalyzer default values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            analyzer = LogAnalyzer(log_file=log_file)

            assert analyzer.log_level_filter is None
            assert analyzer.request_id_filter is None

    def test_init_with_log_level_filter(self):
        """Verify LogAnalyzer initializes with log level filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            analyzer = LogAnalyzer(log_file=log_file, log_level_filter='ERROR')
            assert analyzer.log_level_filter == 'ERROR'

    def test_init_with_request_id_filter(self):
        """Verify LogAnalyzer initializes with request ID filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            analyzer = LogAnalyzer(log_file=log_file, request_id_filter='abc123')
            assert analyzer.request_id_filter == 'abc123'


class TestLogAnalyzerAnalyze:
    """Tests for LogAnalyzer.analyze method."""

    def test_analyze_returns_results(self):
        """Verify analyze returns results dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert isinstance(results, dict)
            assert 'errors' in results
            assert 'security_events' in results
            assert 'communication_issues' in results

    def test_analyze_counts_errors(self):
        """Verify analyze counts errors correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            # Write JSON log entries
            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'test error'}) + '\n')
                f.write(json.dumps({'level': 'INFO', 'event': 'test info'}) + '\n')
                f.write(json.dumps({'level': 'ERROR', 'event': 'another error'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 2

    def test_analyze_counts_security_events(self):
        """Verify analyze counts security events correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            # Write JSON log entries with security events
            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'password_changed'}) + '\n')
                f.write(json.dumps({'level': 'INFO', 'event': 'token_refreshed'}) + '\n')
                f.write(json.dumps({'level': 'INFO', 'event': 'normal_event'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['security_events']) == 2

    def test_analyze_counts_communication_issues(self):
        """Verify analyze counts communication issues correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            # Write JSON log entries with communication issues
            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'WARNING', 'event': 'timeout'}) + '\n')
                f.write(json.dumps({'level': 'WARNING', 'event': 'connection_refused', 'message': 'connection refused'}) + '\n')
                f.write(json.dumps({'level': 'INFO', 'event': 'normal_event'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['communication_issues']) == 2


class TestLogAnalyzerJsonParsing:
    """Tests for JSON log parsing."""

    def test_parses_valid_json_log(self):
        """Verify valid JSON log entries are parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({
                    'timestamp': '2024-01-01T00:00:00Z',
                    'level': 'INFO',
                    'event': 'test_event',
                    'message': 'Test message'
                }) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 0

    def test_handles_invalid_json(self):
        """Verify invalid JSON lines are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('not valid json\n')
                f.write(json.dumps({'level': 'ERROR', 'event': 'test'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            # Should not crash and should find the valid entry
            assert len(results['errors']) == 1

    def test_extracts_standard_fields(self):
        """Verify standard fields are extracted from JSON logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({
                    'timestamp': '2024-01-01T00:00:00Z',
                    'level': 'ERROR',
                    'logger': 'test_logger',
                    'event': 'test_event',
                    'request_id': 'abc123',
                    'component': 'test_component'
                }) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 1
            error = results['errors'][0]
            assert error.get('level') == 'ERROR'
            assert error.get('event') == 'test_event'


class TestLogAnalyzerTextParsing:
    """Tests for text log parsing."""

    def test_parses_text_log(self):
        """Verify text log entries are parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('2024-01-01 00:00:00 - ERROR - Test error message\n')
                f.write('2024-01-01 00:00:01 - INFO - Test info message\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            # Should parse text logs
            assert 'errors' in results

    def test_extracts_level_from_text(self):
        """Verify log level is extracted from text logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('2024-01-01 00:00:00 - ERROR - Test error\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) >= 1


class TestLogAnalyzerErrorDetection:
    """Tests for error category detection."""

    def test_detects_error_level(self):
        """Verify ERROR level entries are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'test'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 1

    def test_detects_critical_level(self):
        """Verify CRITICAL level entries are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'CRITICAL', 'event': 'test'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 1

    def test_detects_error_in_text(self):
        """Verify errors in text logs are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('2024-01-01 ERROR: Something went wrong\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) >= 1


class TestLogAnalyzerSecurityEventDetection:
    """Tests for security event detection."""

    def test_detects_password_event(self):
        """Verify password events are detected as security events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'password_changed'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['security_events']) == 1

    def test_detects_token_event(self):
        """Verify token events are detected as security events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'token_refreshed'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['security_events']) == 1

    def test_detects_auth_event(self):
        """Verify auth events are detected as security events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'user_authenticated'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['security_events']) == 1

    def test_detects_session_event(self):
        """Verify session events are detected as security events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'session_created'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['security_events']) == 1

    def test_detects_security_in_text(self):
        """Verify security events in text logs are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('2024-01-01 INFO: Password changed for user\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['security_events']) >= 1


class TestLogAnalyzerCommunicationIssueDetection:
    """Tests for communication issue detection."""

    def test_detects_timeout(self):
        """Verify timeout events are detected as communication issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'WARNING', 'event': 'timeout'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['communication_issues']) == 1

    def test_detects_connection_refused(self):
        """Verify connection refused events are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'WARNING', 'event': 'connection_refused', 'message': 'connection refused'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['communication_issues']) == 1

    def test_detects_network_error(self):
        """Verify network errors are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'network_error', 'message': 'network error'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['communication_issues']) >= 1

    def test_detects_communication_in_text(self):
        """Verify communication issues in text logs are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('2024-01-01 WARNING: Connection timeout\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['communication_issues']) >= 1


class TestLogAnalyzerRequestIdFiltering:
    """Tests for request ID filtering."""

    def test_filter_by_request_id(self):
        """Verify filtering by request ID works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({
                    'level': 'ERROR',
                    'event': 'test',
                    'request_id': 'abc123'
                }) + '\n')
                f.write(json.dumps({
                    'level': 'ERROR',
                    'event': 'test2',
                    'request_id': 'xyz789'
                }) + '\n')

            analyzer = LogAnalyzer(log_file=log_file, request_id_filter='abc123')
            results = analyzer.analyze()

            # Should only include entries with matching request_id
            for error in results['errors']:
                assert error.get('request_id') == 'abc123'

    def test_no_match_for_request_id(self):
        """Verify no results when request ID doesn't match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({
                    'level': 'ERROR',
                    'event': 'test',
                    'request_id': 'abc123'
                }) + '\n')

            analyzer = LogAnalyzer(log_file=log_file, request_id_filter='nonexistent')
            results = analyzer.analyze()

            # Should have no errors
            assert len(results['errors']) == 0


class TestLogAnalyzerLogLevelFiltering:
    """Tests for log level filtering."""

    def test_filter_by_error_level(self):
        """Verify filtering by ERROR level works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'error1'}) + '\n')
                f.write(json.dumps({'level': 'ERROR', 'event': 'error2'}) + '\n')
                f.write(json.dumps({'level': 'INFO', 'event': 'info1'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file, log_level_filter='ERROR')
            results = analyzer.analyze()

            assert len(results['errors']) == 2

    def test_filter_by_warning_level(self):
        """Verify filtering by WARNING level works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'WARNING', 'event': 'warning1'}) + '\n')
                f.write(json.dumps({'level': 'INFO', 'event': 'info1'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file, log_level_filter='WARNING')
            results = analyzer.analyze()

            assert len(results['warnings']) == 1


class TestLogAnalyzerOutputFormats:
    """Tests for output formats."""

    def test_text_output_format(self):
        """Verify text output format works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'test'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert isinstance(results, dict)

    def test_json_output_format(self):
        """Verify JSON output format works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'test'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert isinstance(results, dict)


class TestPrintReport:
    """Tests for print_report function."""

    def test_print_report_returns_string(self):
        """Verify print_report returns a string."""
        results = {
            'errors': [{'level': 'ERROR', 'event': 'test'}],
            'security_events': [],
            'communication_issues': [],
            'warnings': [],
            'info_events': [],
            'scheduler_events': [],
            'debug_events': [],
            'total_errors': 1,
            'total_security_events': 0,
            'total_communication_issues': 0
        }

        output = print_report(results)
        assert isinstance(output, str)

    def test_print_report_includes_summary(self):
        """Verify print_report includes summary."""
        results = {
            'errors': [{'level': 'ERROR', 'event': 'test'}],
            'security_events': [],
            'communication_issues': [],
            'warnings': [],
            'info_events': [],
            'scheduler_events': [],
            'debug_events': [],
            'total_errors': 1,
            'total_security_events': 0,
            'total_communication_issues': 0
        }

        output = print_report(results)
        assert 'error' in output.lower() or 'summary' in output.lower()


class TestAnalyzeLogsFunction:
    """Tests for analyze_logs convenience function."""

    def test_analyze_logs_returns_results(self):
        """Verify analyze_logs returns results dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            results = analyze_logs(log_file=log_file)

            assert isinstance(results, dict)
            assert 'errors' in results

    def test_analyze_logs_with_log_dir(self):
        """Verify analyze_logs works with log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            results = analyze_logs(log_dir=tmpdir)

            assert isinstance(results, dict)

    def test_analyze_logs_with_filters(self):
        """Verify analyze_logs works with filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': 'test'}) + '\n')

            results = analyze_logs(log_file=log_file, log_level_filter='ERROR')

            assert len(results['errors']) == 1


class TestLogAnalyzerDirectoryScanning:
    """Tests for log directory scanning."""

    def test_scans_directory_for_logs(self):
        """Verify analyzer scans directory for log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple log files
            Path(os.path.join(tmpdir, 'dashboardV2-2024-01-01.log')).touch()
            Path(os.path.join(tmpdir, 'dashboardV2-2024-01-02.log')).touch()

            analyzer = LogAnalyzer(log_dir=tmpdir)
            results = analyzer.analyze()

            assert isinstance(results, dict)

    def test_handles_empty_directory(self):
        """Verify analyzer handles empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = LogAnalyzer(log_dir=tmpdir)
            results = analyzer.analyze()

            assert isinstance(results, dict)


class TestLogAnalyzerSchedulerEvents:
    """Tests for scheduler event detection."""

    def test_detects_scheduler_event(self):
        """Verify scheduler events are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'scheduler_started'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['scheduler_events']) == 1

    def test_detects_server_check_event(self):
        """Verify server check events are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'INFO', 'event': 'server_check_completed'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['scheduler_events']) == 1


class TestLogAnalyzerInfoEvents:
    """Tests for info event detection."""

    def test_limits_info_events(self):
        """Verify info events are limited to 100."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                for i in range(150):
                    f.write(json.dumps({'level': 'INFO', 'event': f'info_{i}'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            # Should limit to 100
            assert len(results['info_events']) <= 100


class TestLogAnalyzerDebugEvents:
    """Tests for debug event detection."""

    def test_detects_debug_events(self):
        """Verify debug events are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({'level': 'DEBUG', 'event': 'debug_info'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['debug_events']) == 1


class TestLogAnalyzerIntegration:
    """Integration tests for log analysis."""

    def test_full_analysis_with_mixed_logs(self):
        """Verify full analysis with mixed log types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                # Errors
                f.write(json.dumps({'level': 'ERROR', 'event': 'error1'}) + '\n')
                f.write(json.dumps({'level': 'ERROR', 'event': 'error2'}) + '\n')
                # Security events
                f.write(json.dumps({'level': 'INFO', 'event': 'password_changed'}) + '\n')
                # Communication issues
                f.write(json.dumps({'level': 'WARNING', 'event': 'timeout'}) + '\n')
                # Info events
                f.write(json.dumps({'level': 'INFO', 'event': 'info1'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 2
            assert len(results['security_events']) == 1
            assert len(results['communication_issues']) == 1

    def test_analysis_with_request_id_correlation(self):
        """Verify analysis with request ID correlation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write(json.dumps({
                    'level': 'ERROR',
                    'event': 'error1',
                    'request_id': 'abc123',
                    'server_url': 'http://localhost:8080'
                }) + '\n')
                f.write(json.dumps({
                    'level': 'INFO',
                    'event': 'info1',
                    'request_id': 'abc123',
                    'server_url': 'http://localhost:8080'
                }) + '\n')

            analyzer = LogAnalyzer(log_file=log_file, request_id_filter='abc123')
            results = analyzer.analyze()

            # Should only include entries with matching request_id
            for error in results['errors']:
                assert error.get('request_id') == 'abc123'


class TestLogAnalyzerEdgeCases:
    """Edge case tests for log analysis."""

    def test_handles_missing_file(self):
        """Verify analyzer handles missing file gracefully."""
        analyzer = LogAnalyzer(log_file='/nonexistent/path.log')
        results = analyzer.analyze()

        assert isinstance(results, dict)

    def test_handles_empty_file(self):
        """Verify analyzer handles empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            Path(log_file).touch()

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert isinstance(results, dict)

    def test_handles_malformed_json(self):
        """Verify analyzer handles malformed JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w') as f:
                f.write('{"level": "ERROR", "event": "valid"}\n')
                f.write('not json at all\n')
                f.write('{"level": "INFO", "event": "also valid"}\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            # Should not crash
            assert isinstance(results, dict)

    def test_handles_unicode_content(self):
        """Verify analyzer handles unicode content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps({'level': 'ERROR', 'event': '用户错误'}) + '\n')

            analyzer = LogAnalyzer(log_file=log_file)
            results = analyzer.analyze()

            assert len(results['errors']) == 1