"""Comprehensive unit tests for the Monitor class.

This module provides complete test coverage for the Monitor class including:
- Monitor initialization and default state
- Start method behavior and state reset
- Attack result reporting and metric aggregation
- Summary and live metrics retrieval
- Thread safety with concurrent operations
- Active thread/socket counter management
- Response time statistics calculation
- HTTP status code tracking
- Time-bucketed hit tracking for hits-per-second

All time-dependent operations are mocked for deterministic testing.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.command import Monitor
from app.models import AttackResult, AttackSummary


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def monitor():
    """Create fresh Monitor instance for each test."""
    return Monitor()


@pytest.fixture
def sample_attack_result():
    """Create sample AttackResult with typical values."""
    return AttackResult(
        num_hits=1,
        http_status=200,
        bytes_sent=500,
        bytes_received=1000,
        response_time_ms=150.5,
        errors=0
    )


# =============================================================================
# TestMonitorInitialization
# =============================================================================

class TestMonitorInitialization:
    """Test default state after initialization."""

    def test_lock_is_threading_lock(self, monitor):
        """Verify _lock is a threading.Lock instance."""
        assert isinstance(monitor._lock, threading.Lock)

    def test_total_hits_starts_at_zero(self, monitor):
        """Verify _total_hits starts at 0."""
        assert monitor._total_hits == 0

    def test_total_bytes_sent_starts_at_zero(self, monitor):
        """Verify _total_bytes_sent starts at 0."""
        assert monitor._total_bytes_sent == 0

    def test_total_bytes_received_starts_at_zero(self, monitor):
        """Verify _total_bytes_received starts at 0."""
        assert monitor._total_bytes_received == 0

    def test_total_errors_starts_at_zero(self, monitor):
        """Verify _total_errors starts at 0."""
        assert monitor._total_errors == 0

    def test_total_requests_starts_at_zero(self, monitor):
        """Verify _total_requests starts at 0."""
        assert monitor._total_requests == 0

    def test_response_times_is_empty_list(self, monitor):
        """Verify _response_times is empty list."""
        assert monitor._response_times == []

    def test_http_status_counts_is_empty_dict(self, monitor):
        """Verify _http_status_counts is empty dict."""
        assert monitor._http_status_counts == {}

    def test_active_threads_starts_at_zero(self, monitor):
        """Verify _active_threads starts at 0."""
        assert monitor._active_threads == 0

    def test_active_sockets_starts_at_zero(self, monitor):
        """Verify _active_sockets starts at 0."""
        assert monitor._active_sockets == 0

    def test_start_time_starts_at_zero(self, monitor):
        """Verify _start_time starts at 0."""
        assert monitor._start_time == 0

    def test_last_http_status_starts_at_zero(self, monitor):
        """Verify _last_http_status starts at 0."""
        assert monitor._last_http_status == 0

    def test_hit_buckets_is_empty_list(self, monitor):
        """Verify _hit_buckets is empty list."""
        assert monitor._hit_buckets == []


# =============================================================================
# TestMonitorStart
# =============================================================================

class TestMonitorStart:
    """Test start() method resets all state correctly."""

    @patch('app.command.time.time')
    def test_start_sets_start_time_to_current_time(self, mock_time, monitor):
        """Test start() sets _start_time to mocked time."""
        mock_time.return_value = 1000.0
        monitor.start()
        assert monitor._start_time == 1000.0

    @patch('app.command.time.time')
    def test_start_sets_last_http_status_to_200(self, mock_time, monitor):
        """Test start() sets _last_http_status to 200."""
        mock_time.return_value = 1000.0
        monitor.start()
        assert monitor._last_http_status == 200

    @patch('app.command.time.time')
    def test_start_initializes_hit_buckets_with_zeros(self, mock_time, monitor):
        """Test start() initializes _hit_buckets with NUM_BUCKETS zeros."""
        mock_time.return_value = 1000.0
        monitor.start()
        assert len(monitor._hit_buckets) == monitor.NUM_BUCKETS
        assert all(bucket == 0 for bucket in monitor._hit_buckets)

    @patch('app.command.time.time')
    def test_start_resets_cumulative_metrics(self, mock_time, monitor):
        """Test start() resets all cumulative metrics to 0."""
        mock_time.return_value = 1000.0
        # Pre-populate some metrics
        monitor._total_hits = 100
        monitor._total_bytes_sent = 5000
        monitor._total_bytes_received = 10000
        monitor._total_errors = 5
        monitor._total_requests = 50
        monitor._response_times = [100.0, 200.0]
        monitor._http_status_counts = {200: 45, 404: 5}
        monitor._active_threads = 10
        monitor._active_sockets = 20

        monitor.start()

        assert monitor._total_hits == 0
        assert monitor._total_bytes_sent == 0
        assert monitor._total_bytes_received == 0
        assert monitor._total_errors == 0
        assert monitor._total_requests == 0
        assert monitor._response_times == []
        assert monitor._http_status_counts == {}
        assert monitor._active_threads == 0
        assert monitor._active_sockets == 0

    @patch('app.command.time.time')
    def test_start_multiple_times_resets_state_each_time(self, mock_time, monitor):
        """Test calling start() multiple times resets state each time."""
        mock_time.return_value = 1000.0
        monitor.start()

        # Add some metrics
        monitor._total_hits = 50
        monitor._total_requests = 25

        # Start again
        mock_time.return_value = 2000.0
        monitor.start()

        assert monitor._start_time == 2000.0
        assert monitor._total_hits == 0
        assert monitor._total_requests == 0


# =============================================================================
# TestReportAttackResult
# =============================================================================

class TestReportAttackResult:
    """Test report_attack_result() with various AttackResult scenarios."""

    # -------------------------------------------------------------------------
    # Basic Metric Aggregation
    # -------------------------------------------------------------------------

    def test_report_increments_total_hits(self, monitor):
        """Test _total_hits increments correctly."""
        result = AttackResult(num_hits=5, bytes_sent=100, bytes_received=200, errors=0)
        monitor.report_attack_result(None, result)
        assert monitor._total_hits == 5

    def test_report_increments_total_bytes_sent(self, monitor):
        """Test _total_bytes_sent increments correctly."""
        result = AttackResult(num_hits=1, bytes_sent=500, bytes_received=200, errors=0)
        monitor.report_attack_result(None, result)
        assert monitor._total_bytes_sent == 500

    def test_report_increments_total_bytes_received(self, monitor):
        """Test _total_bytes_received increments correctly."""
        result = AttackResult(num_hits=1, bytes_sent=100, bytes_received=1000, errors=0)
        monitor.report_attack_result(None, result)
        assert monitor._total_bytes_received == 1000

    def test_report_increments_total_requests(self, monitor):
        """Test _total_requests increments by 1 for each call."""
        result = AttackResult(num_hits=1, bytes_sent=100, bytes_received=200, errors=0)
        monitor.report_attack_result(None, result)
        monitor.report_attack_result(None, result)
        monitor.report_attack_result(None, result)
        assert monitor._total_requests == 3

    def test_report_accumulates_multiple_calls(self, monitor):
        """Test multiple calls accumulate metrics correctly."""
        result1 = AttackResult(num_hits=5, bytes_sent=100, bytes_received=200, errors=0)
        result2 = AttackResult(num_hits=3, bytes_sent=50, bytes_received=100, errors=1)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)

        assert monitor._total_hits == 8
        assert monitor._total_bytes_sent == 150
        assert monitor._total_bytes_received == 300
        assert monitor._total_errors == 1
        assert monitor._total_requests == 2

    # -------------------------------------------------------------------------
    # HTTP Status Tracking
    # -------------------------------------------------------------------------

    def test_report_updates_last_http_status_200(self, monitor):
        """Test _last_http_status updated with 200."""
        result = AttackResult(num_hits=1, http_status=200)
        monitor.report_attack_result(None, result)
        assert monitor._last_http_status == 200

    def test_report_updates_last_http_status_404(self, monitor):
        """Test _last_http_status updated with 404."""
        result = AttackResult(num_hits=1, http_status=404)
        monitor.report_attack_result(None, result)
        assert monitor._last_http_status == 404

    def test_report_http_status_none_does_not_update_last_status(self, monitor):
        """Test _last_http_status not updated when http_status is None."""
        monitor._last_http_status = 200
        result = AttackResult(num_hits=1, http_status=None)
        monitor.report_attack_result(None, result)
        assert monitor._last_http_status == 200

    def test_report_http_status_counts_tracked_separately(self, monitor):
        """Test different status codes tracked separately."""
        result1 = AttackResult(num_hits=1, http_status=200)
        result2 = AttackResult(num_hits=1, http_status=404)
        result3 = AttackResult(num_hits=1, http_status=500)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)
        monitor.report_attack_result(None, result3)

        assert monitor._http_status_counts == {200: 1, 404: 1, 500: 1}

    def test_report_http_status_counts_increments_same_status(self, monitor):
        """Test same status code increments count."""
        result = AttackResult(num_hits=1, http_status=200)

        monitor.report_attack_result(None, result)
        monitor.report_attack_result(None, result)
        monitor.report_attack_result(None, result)

        assert monitor._http_status_counts[200] == 3

    # -------------------------------------------------------------------------
    # Response Time Tracking
    # -------------------------------------------------------------------------

    def test_report_adds_response_time_to_list(self, monitor):
        """Test response_time_ms added to _response_times list."""
        result = AttackResult(num_hits=1, response_time_ms=100.5)
        monitor.report_attack_result(None, result)
        assert monitor._response_times == [100.5]

    def test_report_response_time_none_not_added(self, monitor):
        """Test None response_time_ms not added to list."""
        result = AttackResult(num_hits=1, response_time_ms=None)
        monitor.report_attack_result(None, result)
        assert monitor._response_times == []

    def test_report_multiple_response_times_added(self, monitor):
        """Test multiple response times all added to list."""
        result1 = AttackResult(num_hits=1, response_time_ms=100.0)
        result2 = AttackResult(num_hits=1, response_time_ms=200.0)
        result3 = AttackResult(num_hits=1, response_time_ms=150.0)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)
        monitor.report_attack_result(None, result3)

        assert monitor._response_times == [100.0, 200.0, 150.0]

    # -------------------------------------------------------------------------
    # Error Tracking
    # -------------------------------------------------------------------------

    def test_report_increments_total_errors(self, monitor):
        """Test _total_errors increments with errors=1."""
        result = AttackResult(num_hits=0, errors=1)
        monitor.report_attack_result(None, result)
        assert monitor._total_errors == 1

    def test_report_errors_zero_unchanged(self, monitor):
        """Test _total_errors unchanged with errors=0."""
        result = AttackResult(num_hits=1, errors=0)
        monitor.report_attack_result(None, result)
        assert monitor._total_errors == 0

    # -------------------------------------------------------------------------
    # Hit Bucket Updates
    # -------------------------------------------------------------------------

    @patch('app.command.time.time')
    def test_report_adds_hits_to_current_bucket(self, mock_time, monitor):
        """Test hits added to current bucket based on _current_bucket()."""
        monitor.start()
        mock_time.return_value = 1000.0  # Bucket index 0

        result = AttackResult(num_hits=5)
        monitor.report_attack_result(None, result)

        assert monitor._hit_buckets[0] == 5

    @patch('app.command.time.time')
    def test_report_clears_next_bucket(self, mock_time, monitor):
        """Test next bucket is cleared to 0."""
        monitor.start()
        mock_time.return_value = 1000.0  # Bucket index 0

        # Pre-populate next bucket
        monitor._hit_buckets[1] = 50

        result = AttackResult(num_hits=5)
        monitor.report_attack_result(None, result)

        assert monitor._hit_buckets[1] == 0

    @patch('app.command.time.time')
    def test_report_bucket_wrapping(self, mock_time, monitor):
        """Test bucket wrapping when index reaches NUM_BUCKETS."""
        monitor.start()
        # NUM_BUCKETS is 3, so time 3*BUCKET_SECS = 9 seconds wraps to bucket 0
        mock_time.return_value = 9.0  # (9 / 3) % 3 = 0

        result = AttackResult(num_hits=5)
        monitor.report_attack_result(None, result)

        assert monitor._hit_buckets[0] == 5


# =============================================================================
# TestGetSummary
# =============================================================================

class TestGetSummary:
    """Test get_summary() returns complete AttackSummary."""

    @patch('app.command.time.time')
    def test_get_summary_returns_attack_summary(self, mock_time, monitor):
        """Test get_summary() returns AttackSummary with all metrics."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=10, bytes_sent=500, bytes_received=1000, errors=0)
        monitor.report_attack_result(None, result)

        mock_time.return_value = 1010.0
        summary = monitor.get_summary()

        assert isinstance(summary, AttackSummary)
        assert summary.total_hits == 10
        assert summary.total_bytes_sent == 500
        assert summary.total_bytes_received == 1000
        assert summary.total_errors == 0
        assert summary.total_requests == 1

    @patch('app.command.time.time')
    def test_get_summary_timing_fields(self, mock_time, monitor):
        """Test start_time, end_time, duration_seconds are correct."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1)
        monitor.report_attack_result(None, result)

        mock_time.return_value = 1015.0
        summary = monitor.get_summary()

        assert summary.start_time == 1000.0
        assert summary.end_time == 1015.0
        assert summary.duration_seconds == 15.0

    @patch('app.command.time.time')
    def test_get_summary_active_counters(self, mock_time, monitor):
        """Test active_threads and active_sockets match current values."""
        mock_time.return_value = 1000.0
        monitor.start()

        monitor.increment_active_threads()
        monitor.increment_active_threads()
        monitor.increment_active_sockets(count=5)

        summary = monitor.get_summary()

        assert summary.active_threads == 2
        assert summary.active_sockets == 5

    @patch('app.command.time.time')
    def test_get_summary_http_status_counts_is_copy(self, mock_time, monitor):
        """Test http_status_counts is a copy, not reference."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1, http_status=200)
        monitor.report_attack_result(None, result)

        summary = monitor.get_summary()

        # Modify the copy
        summary.http_status_counts[404] = 5

        # Original should be unchanged
        assert monitor._http_status_counts == {200: 1}

    # -------------------------------------------------------------------------
    # Response Time Statistics
    # -------------------------------------------------------------------------

    @patch('app.command.time.time')
    def test_get_summary_response_time_stats(self, mock_time, monitor):
        """Test response time statistics calculated correctly."""
        mock_time.return_value = 1000.0
        monitor.start()

        result1 = AttackResult(num_hits=1, response_time_ms=100.0)
        result2 = AttackResult(num_hits=1, response_time_ms=200.0)
        result3 = AttackResult(num_hits=1, response_time_ms=150.0)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)
        monitor.report_attack_result(None, result3)

        summary = monitor.get_summary()

        assert summary.avg_response_time_ms == 150.0
        assert summary.min_response_time_ms == 100.0
        assert summary.max_response_time_ms == 200.0

    @patch('app.command.time.time')
    def test_get_summary_no_response_times_none(self, mock_time, monitor):
        """Test all response time fields are None when no response times."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1, response_time_ms=None)
        monitor.report_attack_result(None, result)

        summary = monitor.get_summary()

        assert summary.avg_response_time_ms is None
        assert summary.min_response_time_ms is None
        assert summary.max_response_time_ms is None

    @patch('app.command.time.time')
    def test_get_summary_single_response_time(self, mock_time, monitor):
        """Test avg/min/max all equal single response time value."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1, response_time_ms=150.0)
        monitor.report_attack_result(None, result)

        summary = monitor.get_summary()

        assert summary.avg_response_time_ms == 150.0
        assert summary.min_response_time_ms == 150.0
        assert summary.max_response_time_ms == 150.0

    # -------------------------------------------------------------------------
    # Hits Per Second
    # -------------------------------------------------------------------------

    @patch('app.command.time.time')
    def test_get_summary_hits_per_second(self, mock_time, monitor):
        """Test hits_per_second calculated correctly."""
        mock_time.return_value = 1000.0
        monitor.start()

        for _ in range(50):
            result = AttackResult(num_hits=1)
            monitor.report_attack_result(None, result)

        mock_time.return_value = 1010.0  # 10 seconds
        summary = monitor.get_summary()

        assert summary.hits_per_second == 5.0

    @patch('app.command.time.time')
    def test_get_summary_zero_duration_hits_per_second(self, mock_time, monitor):
        """Test hits_per_second is 0.0 with zero duration."""
        mock_time.return_value = 1000.0
        monitor.start()
        # Don't advance time
        summary = monitor.get_summary()

        assert summary.hits_per_second == 0.0

    # -------------------------------------------------------------------------
    # Thread Safety
    # -------------------------------------------------------------------------

    def test_get_summary_acquires_and_releases_lock(self, monitor):
        """Test get_summary() acquires and releases lock."""
        lock_acquired = []

        def mock_acquire():
            lock_acquired.append(True)

        def mock_release():
            lock_acquired.append(False)

        monitor._lock.acquire = mock_acquire
        monitor._lock.release = mock_release

        with patch('app.command.time.time', return_value=1000.0):
            monitor.get_summary()

        assert lock_acquired == [True, False]

    @patch('app.command.time.time')
    def test_get_summary_does_not_modify_state(self, mock_time, monitor):
        """Test calling get_summary() doesn't modify internal state."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=10, bytes_sent=500, http_status=200)
        monitor.report_attack_result(None, result)

        before_state = (
            monitor._total_hits,
            monitor._total_bytes_sent,
            monitor._http_status_counts.copy()
        )

        monitor.get_summary()

        after_state = (
            monitor._total_hits,
            monitor._total_bytes_sent,
            monitor._http_status_counts.copy()
        )

        assert before_state == after_state


# =============================================================================
# TestGetLiveMetrics
# =============================================================================

class TestGetLiveMetrics:
    """Test get_live_metrics() returns current metrics dictionary."""

    @patch('app.command.time.time')
    def test_get_live_metrics_returns_dict_with_all_keys(self, mock_time, monitor):
        """Test dictionary contains all expected keys."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1, bytes_sent=100, bytes_received=200,
                              http_status=200, response_time_ms=150.0, errors=0)
        monitor.report_attack_result(None, result)

        metrics = monitor.get_live_metrics()

        expected_keys = [
            'total_hits', 'total_bytes_sent', 'total_bytes_received',
            'total_errors', 'total_requests', 'hits_per_second',
            'last_http_status', 'http_status_counts', 'active_threads',
            'active_sockets', 'avg_response_time_ms', 'min_response_time_ms',
            'max_response_time_ms'
        ]

        for key in expected_keys:
            assert key in metrics

    @patch('app.command.time.time')
    def test_get_live_metrics_values_match_state(self, mock_time, monitor):
        """Test values match current state."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=5, bytes_sent=500, bytes_received=1000,
                              http_status=200, response_time_ms=150.0, errors=1)
        monitor.report_attack_result(None, result)

        metrics = monitor.get_live_metrics()

        assert metrics['total_hits'] == 5
        assert metrics['total_bytes_sent'] == 500
        assert metrics['total_bytes_received'] == 1000
        assert metrics['total_errors'] == 1
        assert metrics['total_requests'] == 1
        assert metrics['last_http_status'] == 200

    # -------------------------------------------------------------------------
    # Response Time Statistics
    # -------------------------------------------------------------------------

    @patch('app.command.time.time')
    def test_get_live_metrics_response_time_stats(self, mock_time, monitor):
        """Test avg/min/max calculated correctly."""
        mock_time.return_value = 1000.0
        monitor.start()

        result1 = AttackResult(num_hits=1, response_time_ms=100.0)
        result2 = AttackResult(num_hits=1, response_time_ms=200.0)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)

        metrics = monitor.get_live_metrics()

        assert metrics['avg_response_time_ms'] == 150.0
        assert metrics['min_response_time_ms'] == 100.0
        assert metrics['max_response_time_ms'] == 200.0

    @patch('app.command.time.time')
    def test_get_live_metrics_no_response_times_none(self, mock_time, monitor):
        """Test all response time fields None when no response times."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1, response_time_ms=None)
        monitor.report_attack_result(None, result)

        metrics = monitor.get_live_metrics()

        assert metrics['avg_response_time_ms'] is None
        assert metrics['min_response_time_ms'] is None
        assert metrics['max_response_time_ms'] is None

    # -------------------------------------------------------------------------
    # Hits Per Second
    # -------------------------------------------------------------------------

    @patch('app.command.time.time')
    def test_get_live_metrics_hits_per_second_from_previous_bucket(self, mock_time, monitor):
        """Test hits_per_second uses previous bucket."""
        mock_time.return_value = 0.0
        monitor.start()

        # Add hits to bucket 0 (current at time 0)
        mock_time.return_value = 0.0
        result = AttackResult(num_hits=9)
        monitor.report_attack_result(None, result)

        # At time 3.0, current bucket is (3/3)%3 = 1, previous is 0
        mock_time.return_value = 3.0
        metrics = monitor.get_live_metrics()

        # 9 hits / 3 seconds = 3 hits per second
        assert metrics['hits_per_second'] == 3.0

    # -------------------------------------------------------------------------
    # Dictionary Copy
    # -------------------------------------------------------------------------

    @patch('app.command.time.time')
    def test_get_live_metrics_http_status_counts_is_copy(self, mock_time, monitor):
        """Test http_status_counts is a copy, not reference."""
        mock_time.return_value = 1000.0
        monitor.start()

        result = AttackResult(num_hits=1, http_status=200)
        monitor.report_attack_result(None, result)

        metrics = monitor.get_live_metrics()

        # Modify the copy
        metrics['http_status_counts'][404] = 5

        # Original should be unchanged
        assert monitor._http_status_counts == {200: 1}


# =============================================================================
# TestThreadSafety
# =============================================================================

class TestThreadSafety:
    """Test concurrent metric updates with threading."""

    def test_concurrent_report_attack_result(self, monitor):
        """Test concurrent report_attack_result calls produce correct totals."""
        monitor.start()

        def report_results():
            for _ in range(100):
                result = AttackResult(num_hits=1, bytes_sent=10, bytes_received=20, errors=0)
                monitor.report_attack_result(None, result)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=report_results)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert monitor._total_hits == 1000
        assert monitor._total_bytes_sent == 10000
        assert monitor._total_bytes_received == 20000
        assert monitor._total_requests == 1000

    def test_concurrent_counter_updates(self, monitor):
        """Test concurrent thread counter updates are correct."""
        monitor.start()

        def increment_decrement():
            for _ in range(50):
                monitor.increment_active_threads()
                monitor.decrement_active_threads()

        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment_decrement)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert monitor._active_threads == 0

    def test_concurrent_get_summary_while_reporting(self, monitor):
        """Test get_summary() during concurrent reporting."""
        monitor.start()
        results = []
        errors = []

        def report_results():
            try:
                for _ in range(100):
                    result = AttackResult(num_hits=1, bytes_sent=10, bytes_received=20)
                    monitor.report_attack_result(None, result)
            except Exception as e:
                errors.append(str(e))

        def get_summaries():
            try:
                for _ in range(50):
                    summary = monitor.get_summary()
                    results.append(summary.total_hits)
            except Exception as e:
                errors.append(str(e))

        report_thread = threading.Thread(target=report_results)
        summary_thread = threading.Thread(target=get_summaries)

        report_thread.start()
        summary_thread.start()
        report_thread.join()
        summary_thread.join()

        assert len(errors) == 0
        # Final count should be correct
        assert monitor._total_hits == 100


# =============================================================================
# TestActiveCounters
# =============================================================================

class TestActiveCounters:
    """Test thread/socket counter increment/decrement methods."""

    # -------------------------------------------------------------------------
    # Thread Counters
    # -------------------------------------------------------------------------

    def test_increment_active_threads_increases_by_one(self, monitor):
        """Test increment_active_threads increases _active_threads by 1."""
        monitor.increment_active_threads()
        assert monitor._active_threads == 1

    def test_decrement_active_threads_decreases_by_one(self, monitor):
        """Test decrement_active_threads decreases _active_threads by 1."""
        monitor._active_threads = 5
        monitor.decrement_active_threads()
        assert monitor._active_threads == 4

    def test_multiple_thread_counter_operations(self, monitor):
        """Test multiple increments and decrements."""
        for _ in range(10):
            monitor.increment_active_threads()
        for _ in range(7):
            monitor.decrement_active_threads()
        assert monitor._active_threads == 3

    @patch('app.command.time.time')
    def test_thread_counters_reset_on_start(self, mock_time, monitor):
        """Test thread counters start at 0 after start()."""
        mock_time.return_value = 1000.0
        monitor._active_threads = 10
        monitor.start()
        assert monitor._active_threads == 0

    # -------------------------------------------------------------------------
    # Socket Counters
    # -------------------------------------------------------------------------

    def test_increment_active_sockets_default_count(self, monitor):
        """Test increment_active_sockets with default count=1."""
        monitor.increment_active_sockets()
        assert monitor._active_sockets == 1

    def test_increment_active_sockets_custom_count(self, monitor):
        """Test increment_active_sockets with count=5."""
        monitor.increment_active_sockets(count=5)
        assert monitor._active_sockets == 5

    def test_decrement_active_sockets_default_count(self, monitor):
        """Test decrement_active_sockets with default count=1."""
        monitor._active_sockets = 10
        monitor.decrement_active_sockets()
        assert monitor._active_sockets == 9

    def test_decrement_active_sockets_custom_count(self, monitor):
        """Test decrement_active_sockets with count=3."""
        monitor._active_sockets = 10
        monitor.decrement_active_sockets(count=3)
        assert monitor._active_sockets == 7

    @patch('app.command.time.time')
    def test_socket_counters_reset_on_start(self, mock_time, monitor):
        """Test socket counters start at 0 after start()."""
        mock_time.return_value = 1000.0
        monitor._active_sockets = 15
        monitor.start()
        assert monitor._active_sockets == 0

    # -------------------------------------------------------------------------
    # Thread Safety
    # -------------------------------------------------------------------------

    def test_counter_methods_acquire_and_release_lock(self, monitor):
        """Test each counter method acquires and releases lock."""
        lock_operations = []

        def mock_acquire():
            lock_operations.append('acquire')

        def mock_release():
            lock_operations.append('release')

        monitor._lock.acquire = mock_acquire
        monitor._lock.release = mock_release

        monitor.increment_active_threads()
        monitor.decrement_active_threads()
        monitor.increment_active_sockets()
        monitor.decrement_active_sockets()

        assert lock_operations == ['acquire', 'release', 'acquire', 'release',
                                   'acquire', 'release', 'acquire', 'release']


# =============================================================================
# TestResponseTimeStatistics
# =============================================================================

class TestResponseTimeStatistics:
    """Test response time aggregation (avg, min, max)."""

    @patch('app.command.time.time')
    def test_average_calculation(self, mock_time, monitor):
        """Test average response time calculated correctly."""
        mock_time.return_value = 1000.0
        monitor.start()

        result1 = AttackResult(num_hits=1, response_time_ms=100.0)
        result2 = AttackResult(num_hits=1, response_time_ms=200.0)
        result3 = AttackResult(num_hits=1, response_time_ms=300.0)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)
        monitor.report_attack_result(None, result3)

        summary = monitor.get_summary()
        assert summary.avg_response_time_ms == 200.0

    @patch('app.command.time.time')
    def test_min_max_calculation(self, mock_time, monitor):
        """Test min and max response times calculated correctly."""
        mock_time.return_value = 1000.0
        monitor.start()

        result1 = AttackResult(num_hits=1, response_time_ms=150.0)
        result2 = AttackResult(num_hits=1, response_time_ms=50.0)
        result3 = AttackResult(num_hits=1, response_time_ms=250.0)
        result4 = AttackResult(num_hits=1, response_time_ms=100.0)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)
        monitor.report_attack_result(None, result3)
        monitor.report_attack_result(None, result4)

        summary = monitor.get_summary()
        assert summary.min_response_time_ms == 50.0
        assert summary.max_response_time_ms == 250.0

    @patch('app.command.time.time')
    def test_empty_response_times_none(self, mock_time, monitor):
        """Test all response time fields are None when empty."""
        mock_time.return_value = 1000.0
        monitor.start()

        # Only report results without response times
        result = AttackResult(num_hits=1, response_time_ms=None)
        monitor.report_attack_result(None, result)

        summary = monitor.get_summary()
        assert summary.avg_response_time_ms is None
        assert summary.min_response_time_ms is None
        assert summary.max_response_time_ms is None

    @patch('app.command.time.time')
    def test_mixed_none_and_values(self, mock_time, monitor):
        """Test only non-None values included in statistics."""
        mock_time.return_value = 1000.0
        monitor.start()

        result1 = AttackResult(num_hits=1, response_time_ms=None)
        result2 = AttackResult(num_hits=1, response_time_ms=100.0)
        result3 = AttackResult(num_hits=1, response_time_ms=200.0)
        result4 = AttackResult(num_hits=1, response_time_ms=None)

        monitor.report_attack_result(None, result1)
        monitor.report_attack_result(None, result2)
        monitor.report_attack_result(None, result3)
        monitor.report_attack_result(None, result4)

        summary = monitor.get_summary()
        assert summary.avg_response_time_ms == 150.0
        assert summary.min_response_time_ms == 100.0
        assert summary.max_response_time_ms == 200.0


# =============================================================================
# TestHttpStatusTracking
# =============================================================================

class TestHttpStatusTracking:
    """Test HTTP status code counting."""

    def test_status_code_counting(self, monitor):
        """Test various status codes counted correctly."""
        results = [
            AttackResult(num_hits=1, http_status=200),
            AttackResult(num_hits=1, http_status=200),
            AttackResult(num_hits=1, http_status=404),
            AttackResult(num_hits=1, http_status=500),
            AttackResult(num_hits=1, http_status=200),
        ]

        for result in results:
            monitor.report_attack_result(None, result)

        assert monitor._http_status_counts == {200: 3, 404: 1, 500: 1}

    def test_none_status_not_added_to_counts(self, monitor):
        """Test http_status=None not added to _http_status_counts."""
        monitor._last_http_status = 200  # Set initial value

        result = AttackResult(num_hits=1, http_status=None)
        monitor.report_attack_result(None, result)

        assert monitor._http_status_counts == {}

    def test_none_status_does_not_update_last_status(self, monitor):
        """Test http_status=None doesn't update _last_http_status."""
        monitor._last_http_status = 200

        result = AttackResult(num_hits=1, http_status=None)
        monitor.report_attack_result(None, result)

        assert monitor._last_http_status == 200

    def test_last_status_update_sequence(self, monitor):
        """Test _last_http_status updated correctly in sequence."""
        result1 = AttackResult(num_hits=1, http_status=200)
        result2 = AttackResult(num_hits=1, http_status=404)

        monitor.report_attack_result(None, result1)
        assert monitor._last_http_status == 200

        monitor.report_attack_result(None, result2)
        assert monitor._last_http_status == 404


# =============================================================================
# TestHitBuckets
# =============================================================================

class TestHitBuckets:
    """Test time-bucketed hit tracking for hits-per-second."""

    @patch('app.command.time.time')
    def test_bucket_index_calculation(self, mock_time, monitor):
        """Test _current_bucket() returns correct index."""
        monitor.start()

        # NUM_BUCKETS = 3, BUCKET_SECS = 3
        # Bucket index = int(time / 3) % 3
        mock_time.return_value = 0.0   # int(0/3) % 3 = 0
        assert monitor._current_bucket() == 0

        mock_time.return_value = 3.0   # int(3/3) % 3 = 1
        assert monitor._current_bucket() == 1

        mock_time.return_value = 6.0   # int(6/3) % 3 = 2
        assert monitor._current_bucket() == 2

        mock_time.return_value = 9.0   # int(9/3) % 3 = 0
        assert monitor._current_bucket() == 0

    @patch('app.command.time.time')
    def test_hit_distribution_to_different_buckets(self, mock_time, monitor):
        """Test hits accumulate in correct buckets."""
        monitor.start()

        # Add hits to bucket 0
        mock_time.return_value = 0.0
        result1 = AttackResult(num_hits=5)
        monitor.report_attack_result(None, result1)

        # Add hits to bucket 1
        mock_time.return_value = 3.0
        result2 = AttackResult(num_hits=7)
        monitor.report_attack_result(None, result2)

        # Add hits to bucket 2 - this clears bucket 0 (next bucket wraps around)
        mock_time.return_value = 6.0
        result3 = AttackResult(num_hits=3)
        monitor.report_attack_result(None, result3)

        # bucket0 was cleared when bucket2 was updated (next bucket wraps to 0)
        assert monitor._hit_buckets[0] == 0
        assert monitor._hit_buckets[1] == 7
        assert monitor._hit_buckets[2] == 3

    @patch('app.command.time.time')
    def test_bucket_clearing_next_bucket(self, mock_time, monitor):
        """Test next bucket is cleared to 0."""
        monitor.start()

        # Pre-populate bucket 1
        monitor._hit_buckets[1] = 100

        # Add hits to bucket 0, should clear bucket 1
        mock_time.return_value = 0.0
        result = AttackResult(num_hits=5)
        monitor.report_attack_result(None, result)

        assert monitor._hit_buckets[0] == 5
        assert monitor._hit_buckets[1] == 0

    @patch('app.command.time.time')
    def test_bucket_clearing_wrap_around(self, mock_time, monitor):
        """Test bucket clearing wraps around correctly."""
        monitor.start()

        # Pre-populate bucket 0
        monitor._hit_buckets[0] = 100

        # Add hits to bucket 2 (at time 6.0), should clear bucket 0
        mock_time.return_value = 6.0
        result = AttackResult(num_hits=5)
        monitor.report_attack_result(None, result)

        assert monitor._hit_buckets[2] == 5
        assert monitor._hit_buckets[0] == 0

    @patch('app.command.time.time')
    def test_get_status_uses_previous_bucket(self, mock_time, monitor):
        """Test get_status() uses previous bucket for hits-per-second."""
        monitor.start()

        # Add hits to bucket 0 at time 0
        mock_time.return_value = 0.0
        result = AttackResult(num_hits=9)
        monitor.report_attack_result(None, result)

        # At time 3.0, current bucket is 1, previous is 0
        mock_time.return_value = 3.0
        status, hits_per_sec = monitor.get_status()

        # 9 hits from previous bucket / 3 seconds = 3 hits/sec
        assert hits_per_sec == 3.0


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('app.command.time.time')
    def test_get_summary_before_start_handles_zero_duration(self, mock_time, monitor):
        """Test get_summary() handles zero duration before start()."""
        mock_time.return_value = 1000.0
        # Don't call start()
        summary = monitor.get_summary()
        assert summary.duration_seconds is None
        assert summary.hits_per_second == 0.0

    def test_report_attack_result_before_start_still_works(self, monitor):
        """Test report_attack_result() works before start()."""
        result = AttackResult(num_hits=5, bytes_sent=100, bytes_received=200, errors=0)
        monitor.report_attack_result(None, result)

        assert monitor._total_hits == 5
        assert monitor._total_bytes_sent == 100
        assert monitor._total_bytes_received == 200
        assert monitor._total_requests == 1

    @patch('app.command.time.time')
    def test_very_large_metric_values(self, mock_time, monitor):
        """Test very large metric values handled correctly."""
        mock_time.return_value = 1000.0
        monitor.start()

        large_result = AttackResult(
            num_hits=1000000,
            bytes_sent=10**12,
            bytes_received=10**12,
            errors=999999
        )
        monitor.report_attack_result(None, large_result)

        assert monitor._total_hits == 1000000
        assert monitor._total_bytes_sent == 10**12
        assert monitor._total_bytes_received == 10**12
        assert monitor._total_errors == 999999

    @patch('app.command.time.time')
    def test_empty_attack_result(self, mock_time, monitor):
        """Test empty AttackResult (all zeros) doesn't break aggregation."""
        mock_time.return_value = 1000.0
        monitor.start()

        empty_result = AttackResult(
            num_hits=0,
            http_status=None,
            bytes_sent=0,
            bytes_received=0,
            response_time_ms=None,
            errors=0
        )
        monitor.report_attack_result(None, empty_result)

        assert monitor._total_hits == 0
        assert monitor._total_bytes_sent == 0
        assert monitor._total_bytes_received == 0
        assert monitor._total_errors == 0
        assert monitor._total_requests == 1

    @patch('app.command.time.time')
    def test_negative_time_difference_handled_gracefully(self, mock_time, monitor):
        """Test negative time differences handled gracefully."""
        # Set start time in the future (simulating clock skew)
        mock_time.return_value = 2000.0
        monitor.start()

        # Now go back in time
        mock_time.return_value = 1000.0
        summary = monitor.get_summary()

        # Should handle negative duration by returning None for duration and 0.0 for hits_per_second
        assert summary.duration_seconds is None
        assert summary.hits_per_second == 0.0
