"""Unit tests for the SummaryReporter class.

This module contains comprehensive tests for the SummaryReporter,
following the established patterns from test_monitor.py. Tests cover
display output, formatting helpers, and edge cases.

Test Classes:
    TestSummaryReporter: Main test class containing all reporter tests.

Fixtures:
    reporter: Creates a SummaryReporter instance.
    attack_summary_full: Creates a complete AttackSummary with all metrics.
    attack_summary_slowloris: Creates a slowloris AttackSummary (no response times).
    attack_summary_empty: Creates an empty/minimal AttackSummary.
"""

import pytest
from unittest.mock import patch
from datetime import datetime

from app.reporter import SummaryReporter
from app.models import AttackSummary


class TestSummaryReporter:
    """Tests for SummaryReporter class."""

    @pytest.fixture
    def reporter(self):
        """Create a SummaryReporter instance."""
        return SummaryReporter()

    @pytest.fixture
    def attack_summary_full(self):
        """Create a complete AttackSummary with all metrics."""
        return AttackSummary(
            total_hits=1000,
            total_requests=1200,
            total_bytes_sent=1572864,  # 1.5 MB
            total_bytes_received=3145728,  # 3 MB
            total_errors=50,
            avg_response_time_ms=245.5,
            min_response_time_ms=100.0,
            max_response_time_ms=500.0,
            hits_per_second=16.67,
            http_status_counts={200: 1000, 404: 150, 500: 50},
            active_threads=10,
            active_sockets=0,
            start_time=1609459200.0,  # 2021-01-01 00:00:00
            end_time=1609459260.5,  # 2021-01-01 00:01:00.5
            duration_seconds=60.5
        )

    @pytest.fixture
    def attack_summary_slowloris(self):
        """Create a slowloris AttackSummary (no response times)."""
        return AttackSummary(
            total_hits=500,
            total_requests=500,
            total_bytes_sent=102400,
            total_bytes_received=51200,
            total_errors=0,
            avg_response_time_ms=None,
            min_response_time_ms=None,
            max_response_time_ms=None,
            hits_per_second=8.33,
            http_status_counts={},
            active_threads=50,
            active_sockets=1000,
            start_time=1609459200.0,
            end_time=1609459260.0,
            duration_seconds=60.0
        )

    @pytest.fixture
    def attack_summary_empty(self):
        """Create an empty/minimal AttackSummary."""
        return AttackSummary()

    # =====================================================================
    # Display Tests
    # =====================================================================

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_shows_all_metrics(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that all metrics from AttackSummary are displayed."""
        reporter.display(attack_summary_full)
        
        # Verify key metrics are logged
        mock_log.assert_any_call('  Total Hits: 1000')
        mock_log.assert_any_call('  Total Requests: 1200')
        mock_log.assert_any_call(f"  Avg Response Time: {attack_summary_full.avg_response_time_ms:.2f} ms")

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_calls_console_methods(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that console methods are called appropriately."""
        reporter.display(attack_summary_full)
        
        # hr() should be called for header and footer
        assert mock_hr.call_count >= 2
        # system() should be called for section headers
        assert mock_system.called
        # log() should be called for metrics
        assert mock_log.called

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_formats_bytes_correctly(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that bytes are formatted to KB/MB/GB."""
        reporter.display(attack_summary_full)
        
        # 1572864 bytes = 1.50 MB
        mock_log.assert_any_call('  Bytes Sent: 1.50 MB')
        # 3145728 bytes = 3.00 MB
        mock_log.assert_any_call('  Bytes Received: 3.00 MB')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_formats_duration_correctly(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that duration is formatted correctly."""
        reporter.display(attack_summary_full)
        
        # 60.5 seconds should be formatted as "0h 1m 0s"
        mock_log.assert_any_call('  Duration: 0h 1m 0s')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_formats_timestamps_correctly(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that timestamps are formatted to readable dates."""
        reporter.display(attack_summary_full)
        
        mock_log.assert_any_call('  Start Time: 2021-01-01 00:00:00')
        mock_log.assert_any_call('  End Time: 2021-01-01 00:01:00')

    # =====================================================================
    # Response Time Tests
    # =====================================================================

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_shows_response_times_when_available(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that avg/min/max response times are displayed when not None."""
        reporter.display(attack_summary_full)
        
        mock_log.assert_any_call('  Avg Response Time: 245.50 ms')
        mock_log.assert_any_call('  Min Response Time: 100.00 ms')
        mock_log.assert_any_call('  Max Response Time: 500.00 ms')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_shows_na_for_response_times_when_none(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_slowloris
    ):
        """Test that 'N/A' is displayed for slowloris mode (None response times)."""
        reporter.display(attack_summary_slowloris)
        
        mock_log.assert_any_call('  Avg Response Time: N/A')
        mock_log.assert_any_call('  Min Response Time: N/A')
        mock_log.assert_any_call('  Max Response Time: N/A')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_handles_mixed_response_times(
        self, mock_system, mock_log, mock_hr, reporter
    ):
        """Test that partial None values are handled correctly."""
        summary = AttackSummary(
            avg_response_time_ms=100.0,
            min_response_time_ms=None,
            max_response_time_ms=500.0
        )
        reporter.display(summary)
        
        mock_log.assert_any_call('  Avg Response Time: 100.00 ms')
        mock_log.assert_any_call('  Min Response Time: N/A')
        mock_log.assert_any_call('  Max Response Time: 500.00 ms')

    # =====================================================================
    # HTTP Status Distribution Tests
    # =====================================================================

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_shows_http_status_counts(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_full
    ):
        """Test that HTTP status codes and counts are displayed."""
        reporter.display(attack_summary_full)
        
        mock_log.assert_any_call('  HTTP 200: 1000 requests')
        mock_log.assert_any_call('  HTTP 404: 150 requests')
        mock_log.assert_any_call('  HTTP 500: 50 requests')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_handles_empty_status_counts(
        self, mock_system, mock_log, mock_hr, reporter, attack_summary_slowloris
    ):
        """Test that empty status_counts is handled gracefully."""
        reporter.display(attack_summary_slowloris)
        
        mock_log.assert_any_call('  No HTTP status codes recorded')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_shows_multiple_status_codes(
        self, mock_system, mock_log, mock_hr, reporter
    ):
        """Test that multiple status codes are displayed correctly."""
        summary = AttackSummary(
            http_status_counts={200: 500, 301: 50, 302: 30, 404: 20}
        )
        reporter.display(summary)
        
        mock_log.assert_any_call('  HTTP 200: 500 requests')
        mock_log.assert_any_call('  HTTP 301: 50 requests')
        mock_log.assert_any_call('  HTTP 302: 30 requests')
        mock_log.assert_any_call('  HTTP 404: 20 requests')

    # =====================================================================
    # Edge Cases
    # =====================================================================

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_handles_none_duration(
        self, mock_system, mock_log, mock_hr, reporter
    ):
        """Test that None duration is handled gracefully."""
        summary = AttackSummary(duration_seconds=None)
        reporter.display(summary)
        
        mock_log.assert_any_call('  Duration: N/A')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_handles_zero_values(
        self, mock_system, mock_log, mock_hr, reporter
    ):
        """Test that zero values are displayed correctly."""
        summary = AttackSummary(
            total_hits=0,
            total_requests=0,
            total_bytes_sent=0,
            total_bytes_received=0,
            total_errors=0,
            hits_per_second=0.0,
            duration_seconds=0.0
        )
        reporter.display(summary)
        
        mock_log.assert_any_call('  Total Hits: 0')
        mock_log.assert_any_call('  Total Requests: 0')
        mock_log.assert_any_call('  Bytes Sent: 0 B')
        mock_log.assert_any_call('  Bytes Received: 0 B')
        mock_log.assert_any_call('  Hits per Second: 0.00 hits/sec')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_handles_large_numbers(
        self, mock_system, mock_log, mock_hr, reporter
    ):
        """Test that large byte counts are formatted correctly (GB/TB)."""
        summary = AttackSummary(
            total_bytes_sent=1610612736,  # 1.50 GB
            total_bytes_received=1099511627776  # 1.00 TB
        )
        reporter.display(summary)
        
        mock_log.assert_any_call('  Bytes Sent: 1.50 GB')
        mock_log.assert_any_call('  Bytes Received: 1.00 TB')

    @patch('app.reporter.app.console.hr')
    @patch('app.reporter.app.console.log')
    @patch('app.reporter.app.console.system')
    def test_display_active_sockets_only_when_nonzero(
        self, mock_system, mock_log, mock_hr, reporter
    ):
        """Test that active sockets are only shown if > 0."""
        # Test with active_sockets = 0
        summary_no_sockets = AttackSummary(active_sockets=0)
        reporter.display(summary_no_sockets)
        
        # Check that active sockets message is NOT logged when 0
        for call in mock_log.call_args_list:
            assert 'Active Sockets' not in call[0][0]
        
        # Reset mocks and test with active_sockets > 0
        mock_log.reset_mock()
        summary_with_sockets = AttackSummary(active_sockets=100)
        reporter.display(summary_with_sockets)
        
        mock_log.assert_any_call('  Active Sockets: 100')

    # =====================================================================
    # Formatting Helper Tests
    # =====================================================================

    def test_format_bytes_kb(self, reporter):
        """Test bytes to KB conversion."""
        result = reporter._format_bytes(1536)  # 1.5 KB
        assert result == '1.50 KB'

    def test_format_bytes_mb(self, reporter):
        """Test bytes to MB conversion."""
        result = reporter._format_bytes(1572864)  # 1.5 MB
        assert result == '1.50 MB'

    def test_format_bytes_gb(self, reporter):
        """Test bytes to GB conversion."""
        result = reporter._format_bytes(1610612736)  # 1.5 GB
        assert result == '1.50 GB'

    def test_format_bytes_tb(self, reporter):
        """Test bytes to TB conversion."""
        result = reporter._format_bytes(1649267441664)  # 1.5 TB
        assert result == '1.50 TB'

    def test_format_bytes_zero(self, reporter):
        """Test zero bytes formatting."""
        result = reporter._format_bytes(0)
        assert result == '0 B'

    def test_format_bytes_negative(self, reporter):
        """Test negative bytes formatting."""
        result = reporter._format_bytes(-100)
        assert result == '0 B'

    def test_format_duration_seconds(self, reporter):
        """Test seconds-only formatting."""
        result = reporter._format_duration(45.5)
        assert result == '45.50 seconds'

    def test_format_duration_minutes(self, reporter):
        """Test minutes and seconds formatting."""
        result = reporter._format_duration(125.5)
        assert result == '0h 2m 5s'

    def test_format_duration_hours(self, reporter):
        """Test hours, minutes, seconds formatting."""
        result = reporter._format_duration(3665.0)
        assert result == '1h 1m 5s'

    def test_format_duration_none(self, reporter):
        """Test None duration formatting."""
        result = reporter._format_duration(None)
        assert result == 'N/A'

    def test_format_timestamp(self, reporter):
        """Test Unix timestamp to readable format."""
        result = reporter._format_timestamp(1609459200)
        assert result == '2021-01-01 00:00:00'

    def test_format_timestamp_none(self, reporter):
        """Test None timestamp formatting."""
        result = reporter._format_timestamp(None)
        assert result == 'N/A'
