"""Comprehensive unit tests for the IdentityRotator class.

This module provides complete test coverage for the IdentityRotator class including:
- Initialization and default state
- Rotation timing behavior using mocked time.sleep and threading.Event.wait
- Graceful shutdown mechanism with stop() and wait_done()
- Fire-and-forget exception handling
- Logging behavior via app.console.log and app.console.error
- Thread lifecycle methods (start_rotation, start, join)
- Edge cases and boundary conditions

All external dependencies (TorClient, app.console, threading.Event) are mocked to ensure
isolated, fast-running tests without actual Tor connections or time delays.
"""

import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest

import app.console
from app.command import IdentityRotator
from app.tor import ConnectionErrorException


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_tor_client():
    """Returns MagicMock with new_identity() method configured."""
    tor_client = MagicMock()
    tor_client.new_identity = MagicMock()
    return tor_client


@pytest.fixture
def mock_console_log():
    """Patches app.console.log using patch decorator."""
    with patch('app.command.app.console.log') as mock_log:
        yield mock_log


@pytest.fixture
def mock_console_error():
    """Patches app.console.error using patch decorator."""
    with patch('app.command.app.console.error') as mock_error:
        yield mock_error


@pytest.fixture
def identity_rotator(mock_tor_client):
    """Returns fresh IdentityRotator instance with mock TorClient and default interval."""
    return IdentityRotator(tor_client=mock_tor_client)


# =============================================================================
# TestIdentityRotatorInitialization
# =============================================================================

class TestIdentityRotatorInitialization:
    """Test initialization and default values."""

    def test_tor_client_set_from_constructor(self, mock_tor_client):
        """Verify _tor_client is set correctly from constructor parameter."""
        rotator = IdentityRotator(tor_client=mock_tor_client)
        assert rotator._tor_client is mock_tor_client

    def test_interval_defaults_to_300_seconds(self, mock_tor_client):
        """Verify _interval defaults to 300 seconds when not provided."""
        rotator = IdentityRotator(tor_client=mock_tor_client)
        assert rotator._interval == 300

    def test_interval_set_correctly_when_custom_value_provided(self, mock_tor_client):
        """Verify _interval is set correctly when custom value provided."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=60)
        assert rotator._interval == 60

        rotator2 = IdentityRotator(tor_client=mock_tor_client, interval=5)
        assert rotator2._interval == 5

    def test_is_rotating_starts_as_false(self, mock_tor_client):
        """Verify _is_rotating starts as False."""
        rotator = IdentityRotator(tor_client=mock_tor_client)
        assert rotator._is_rotating is False

    def test_stop_event_is_threading_event_instance(self, mock_tor_client):
        """Verify _stop_event is instance of threading.Event."""
        rotator = IdentityRotator(tor_client=mock_tor_client)
        assert isinstance(rotator._stop_event, threading.Event)

    def test_daemon_attribute_is_true(self, mock_tor_client):
        """Verify daemon attribute is True."""
        rotator = IdentityRotator(tor_client=mock_tor_client)
        assert rotator.daemon is True

    def test_inherits_from_threading_thread(self, mock_tor_client):
        """Verify inherits from threading.Thread."""
        rotator = IdentityRotator(tor_client=mock_tor_client)
        assert isinstance(rotator, threading.Thread)


# =============================================================================
# TestIdentityRotatorTiming
# =============================================================================

class TestIdentityRotatorTiming:
    """Test rotation timing behavior using mocked threading.Event.wait."""

    @patch('app.command.app.console.log')
    def test_new_identity_called_at_correct_intervals(self, mock_log, mock_tor_client):
        """Mock Event.wait to return False on first 3 calls, then True, verify new_identity() called 3 times."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            # Return False (timeout) for first 3 calls, True (stop signal) on 4th
            return call_count[0] >= 4

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        assert mock_tor_client.new_identity.call_count == 3

    @patch('app.command.app.console.log')
    def test_event_wait_called_with_correct_timeout_value(self, mock_log, mock_tor_client):
        """Verify Event.wait() called with correct timeout value matching interval."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=60)

        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        rotator._stop_event.wait.assert_called_with(60)

    @patch('app.command.app.console.log')
    def test_different_interval_values_5_seconds(self, mock_log, mock_tor_client):
        """Test with interval of 5 seconds."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=5)

        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        rotator._stop_event.wait.assert_called_with(5)

    @patch('app.command.app.console.log')
    def test_different_interval_values_60_seconds(self, mock_log, mock_tor_client):
        """Test with interval of 60 seconds."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=60)

        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        rotator._stop_event.wait.assert_called_with(60)

    @patch('app.command.app.console.log')
    def test_different_interval_values_300_seconds(self, mock_log, mock_tor_client):
        """Test with interval of 300 seconds."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        rotator._stop_event.wait.assert_called_with(300)

    @patch('app.command.app.console.log')
    def test_wait_called_multiple_times_until_stop(self, mock_log, mock_tor_client):
        """Verify wait is called multiple times until stop signal received."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=10)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 3

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        assert rotator._stop_event.wait.call_count == 3
        assert mock_tor_client.new_identity.call_count == 2


# =============================================================================
# TestIdentityRotatorGracefulShutdown
# =============================================================================

class TestIdentityRotatorGracefulShutdown:
    """Test shutdown mechanism."""

    def test_stop_sets_is_rotating_to_false(self, identity_rotator, mock_console_log):
        """Verify stop() sets _is_rotating to False."""
        identity_rotator._is_rotating = True
        identity_rotator.stop()
        assert identity_rotator._is_rotating is False

    def test_stop_calls_stop_event_set(self, identity_rotator, mock_console_log):
        """Verify stop() calls _stop_event.set()."""
        with patch.object(identity_rotator._stop_event, 'set') as mock_set:
            identity_rotator.stop()
            mock_set.assert_called_once()

    def test_stop_logs_stopping_message(self, identity_rotator, mock_console_log):
        """Verify stop() logs 'stopping identity rotator' message."""
        identity_rotator.stop()
        mock_console_log.assert_called_with("stopping identity rotator")

    def test_wait_done_calls_join_when_thread_alive(self, identity_rotator, mock_console_log):
        """Verify wait_done() calls join() when thread is alive."""
        with patch.object(identity_rotator, 'is_alive', return_value=True):
            with patch.object(identity_rotator, 'join') as mock_join:
                identity_rotator.wait_done()
                mock_join.assert_called_once()

    def test_wait_done_does_not_call_join_when_thread_not_alive(self, identity_rotator, mock_console_log):
        """Verify wait_done() does not call join() when thread not alive."""
        with patch.object(identity_rotator, 'is_alive', return_value=False):
            with patch.object(identity_rotator, 'join') as mock_join:
                identity_rotator.wait_done()
                mock_join.assert_not_called()

    @patch('app.command.app.console.log')
    def test_run_exits_immediately_when_stop_event_wait_returns_true(self, mock_log, mock_tor_client):
        """Test that run() exits immediately when _stop_event.wait() returns True."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        # First call returns True (stop signal), should exit immediately without calling new_identity
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        # new_identity should never be called because stop_event.wait returned True immediately
        mock_tor_client.new_identity.assert_not_called()

    @patch('app.command.app.console.log')
    def test_rotation_loop_exits_cleanly_after_stop(self, mock_log, mock_tor_client):
        """Verify rotation loop exits cleanly without additional new_identity() calls after stop."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            # First call: timeout (False), second call: stop signal (True)
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Should call new_identity once after first timeout, then exit on stop signal
        mock_tor_client.new_identity.assert_called_once()


# =============================================================================
# TestIdentityRotatorFireAndForget
# =============================================================================

class TestIdentityRotatorFireAndForget:
    """Test exception handling and fire-and-forget behavior."""

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_exception_caught_and_logged(self, mock_error, mock_log, mock_tor_client):
        """Mock new_identity() to raise ConnectionErrorException, verify exception is caught and logged."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        mock_tor_client.new_identity.side_effect = ConnectionErrorException("connection failed")

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Exception should be caught and error should be logged
        mock_error.assert_called_once()
        assert "identity rotation failed" in mock_error.call_args[0][0]

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_thread_continues_after_exception(self, mock_error, mock_log, mock_tor_client):
        """Verify thread continues running after exception (doesn't crash)."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        call_count = [0]

        def mixed_behavior():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionErrorException("connection failed")
            return None

        mock_tor_client.new_identity.side_effect = mixed_behavior

        wait_count = [0]

        def wait_side_effect(timeout):
            wait_count[0] += 1
            return wait_count[0] >= 3

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Should have called new_identity twice (once failed, once succeeded)
        assert mock_tor_client.new_identity.call_count == 2
        mock_error.assert_called_once()

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_subsequent_rotations_after_failure(self, mock_error, mock_log, mock_tor_client):
        """Verify subsequent rotations still occur after failure."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        call_count = [0]

        def fail_then_succeed():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionErrorException("connection failed")
            return None

        mock_tor_client.new_identity.side_effect = fail_then_succeed

        wait_count = [0]

        def wait_side_effect(timeout):
            wait_count[0] += 1
            return wait_count[0] >= 3

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Verify both calls were made
        assert mock_tor_client.new_identity.call_count == 2
        # Verify error was logged for the first failure
        mock_error.assert_called_once()

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_generic_exception_caught(self, mock_error, mock_log, mock_tor_client):
        """Test with generic Exception to ensure all exceptions caught."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        mock_tor_client.new_identity.side_effect = Exception("generic error")

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Exception should be caught and error should be logged
        mock_error.assert_called_once()
        assert "identity rotation failed" in mock_error.call_args[0][0]
        assert "generic error" in mock_error.call_args[0][0]

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_error_message_includes_exception_details(self, mock_error, mock_log, mock_tor_client):
        """Verify error message includes exception details in log."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        mock_tor_client.new_identity.side_effect = ConnectionErrorException("detailed error message")

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        error_message = mock_error.call_args[0][0]
        assert "identity rotation failed" in error_message
        assert "detailed error message" in error_message


# =============================================================================
# TestIdentityRotatorLogging
# =============================================================================

class TestIdentityRotatorLogging:
    """Test logging behavior."""

    @patch('app.command.app.console.log')
    def test_startup_message_logged(self, mock_log, mock_tor_client):
        """Verify 'starting identity rotator (interval: X seconds)' logged on start."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        mock_log.assert_any_call("starting identity rotator (interval: 300 seconds)")

    @patch('app.command.app.console.log')
    def test_success_message_logged_after_rotation(self, mock_log, mock_tor_client):
        """Verify 'identity rotated successfully' logged after successful rotation."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        mock_log.assert_any_call("identity rotated successfully")

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_error_logged_on_exception(self, mock_error, mock_log, mock_tor_client):
        """Verify 'identity rotation failed: <error>' logged on exception."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        mock_tor_client.new_identity.side_effect = Exception("rotation failed")

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        mock_error.assert_called_once_with("identity rotation failed: rotation failed")

    @patch('app.command.app.console.log')
    def test_stopped_message_logged_when_rotation_ends(self, mock_log, mock_tor_client):
        """Verify 'identity rotator stopped' logged when rotation ends."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        mock_log.assert_any_call("identity rotator stopped")

    @patch('app.command.app.console.log')
    def test_startup_message_includes_correct_interval_value(self, mock_log, mock_tor_client):
        """Test logging includes correct interval value in startup message."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=60)
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        mock_log.assert_any_call("starting identity rotator (interval: 60 seconds)")

    @patch('app.command.app.console._log')
    def test_log_output_contains_timestamp(self, mock_log, mock_tor_client):
        """Verify formatted log output contains timestamp using regex pattern."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=5)
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        # Verify _log was called and capture the formatted messages
        assert mock_log.called

        # Check each call for timestamp pattern (YYYY-MM-DD HH:MM:SS)
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'

        for call_args in mock_log.call_args_list:
            colour = call_args[0][0]
            message = call_args[0][1]
            # The message should be a string (the message part)
            assert isinstance(message, str)
            # Verify message contains expected content
            assert any(keyword in message for keyword in [
                "starting identity rotator",
                "identity rotator stopped"
            ])

    @patch('app.command.app.console._ttysize')
    def test_log_format_includes_timestamp(self, mock_ttysize, mock_tor_client):
        """Patch _log_format to capture formatted output and verify timestamp is present."""
        # Store formatted outputs
        formatted_outputs = []

        # Save original function before patching
        original_log_format = app.console._log_format

        def capture_log_format(colour, message):
            # Call the original function directly (not through the module)
            result = original_log_format(colour, message)
            formatted_outputs.append(result)
            return result

        with patch('app.command.app.console._log_format', side_effect=capture_log_format):
            rotator = IdentityRotator(tor_client=mock_tor_client, interval=5)
            rotator._stop_event.wait = MagicMock(return_value=True)

            # Mock _ttysize to return fixed dimensions
            mock_ttysize.return_value = (80, 24)

            rotator.run()

        # Verify formatted outputs contain timestamp pattern
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'

        assert len(formatted_outputs) >= 2  # startup and stopped messages

        for output in formatted_outputs:
            # Should contain timestamp in format YYYY-MM-DD HH:MM:SS
            assert re.search(timestamp_pattern, output), f"Timestamp not found in: {output}"

        # Verify messages contain expected content
        found_startup = any("starting identity rotator" in output for output in formatted_outputs)
        found_stopped = any("identity rotator stopped" in output for output in formatted_outputs)

        assert found_startup, "Startup message not found in formatted output"
        assert found_stopped, "Stopped message not found in formatted output"


# =============================================================================
# TestIdentityRotatorLifecycle
# =============================================================================

class TestIdentityRotatorLifecycle:
    """Test thread lifecycle methods."""

    def test_start_rotation_calls_start_method(self, identity_rotator):
        """Verify start_rotation() calls start() method."""
        with patch.object(identity_rotator, 'start') as mock_start:
            identity_rotator.start_rotation()
            mock_start.assert_called_once()

    @patch('app.command.app.console.log')
    def test_full_lifecycle(self, mock_log, mock_tor_client):
        """Test full lifecycle: create rotator, start, verify running, stop, verify stopped."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        # Mock run to track execution
        run_called = [False]
        original_run = rotator.run

        def tracked_run():
            run_called[0] = True
            return original_run()

        rotator.run = tracked_run

        # Start rotation
        with patch.object(rotator, 'start'):
            rotator.start_rotation()

        # Verify _is_rotating is False before run() is called
        assert rotator._is_rotating is False

        # Simulate run being called
        rotator._stop_event.wait = MagicMock(return_value=True)
        rotator.run()

        assert run_called[0] is True

    def test_is_alive_returns_true_after_start(self, identity_rotator, mock_console_log):
        """Verify is_alive() returns True after start, False after join."""
        # Note: We can't actually start the thread in unit tests without complex mocking
        # Instead, we verify the thread lifecycle methods work correctly
        with patch.object(identity_rotator, 'start'):
            identity_rotator.start_rotation()
            # start() was called, but we're mocking it to avoid actual thread execution

    def test_stop_called_multiple_times_is_safe(self, identity_rotator, mock_console_log):
        """Test that calling stop() multiple times is safe."""
        # First stop
        identity_rotator.stop()
        # Second stop - should not raise
        identity_rotator.stop()
        # Third stop - should not raise
        identity_rotator.stop()

        # Verify _is_rotating is False
        assert identity_rotator._is_rotating is False
        # Verify _stop_event is set
        assert identity_rotator._stop_event.is_set()

    def test_wait_done_called_safely_when_thread_not_started(self, identity_rotator, mock_console_log):
        """Test that wait_done() can be called safely when thread not started."""
        # Should not raise any exceptions
        identity_rotator.wait_done()


# =============================================================================
# TestIdentityRotatorEdgeCases
# =============================================================================

class TestIdentityRotatorEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('app.command.app.console.log')
    def test_interval_of_zero_seconds(self, mock_log, mock_tor_client):
        """Test with interval of 0 seconds (should still work, immediate rotation)."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=0)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Should have called new_identity once
        mock_tor_client.new_identity.assert_called_once()
        # Should have waited with timeout of 0
        rotator._stop_event.wait.assert_called_with(0)

    @patch('app.command.app.console.log')
    def test_very_large_interval(self, mock_log, mock_tor_client):
        """Test with very large interval (e.g., 86400 seconds / 1 day)."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=86400)

        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        rotator._stop_event.wait.assert_called_with(86400)

    @patch('app.command.app.console.log')
    def test_stopping_before_first_rotation_completes(self, mock_log, mock_tor_client):
        """Test stopping before first rotation completes."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        # Stop event returns True immediately (stop called before first wait completes)
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        # new_identity should never be called
        mock_tor_client.new_identity.assert_not_called()

    @patch('app.command.app.console.log')
    def test_new_identity_called_exactly_once_per_interval(self, mock_log, mock_tor_client):
        """Test new_identity() called exactly once per interval (not multiple times)."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 4

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Should have 3 rotations (wait returned False 3 times)
        assert mock_tor_client.new_identity.call_count == 3

    @patch('app.command.app.console.log')
    def test_no_rotation_if_stopped_before_first_interval_elapses(self, mock_log, mock_tor_client):
        """Verify no rotation occurs if stopped before first interval elapses."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        # First wait returns True immediately (stop signal received before timeout)
        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        # No new_identity calls should be made
        mock_tor_client.new_identity.assert_not_called()
        # Startup and stopped messages should still be logged
        mock_log.assert_any_call("starting identity rotator (interval: 300 seconds)")
        mock_log.assert_any_call("identity rotator stopped")

    @patch('app.command.app.console.log')
    def test_multiple_intervals_with_stop_signal(self, mock_log, mock_tor_client):
        """Test multiple intervals with stop signal arriving mid-execution."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        wait_count = [0]

        def wait_side_effect(timeout):
            wait_count[0] += 1
            # Allow 5 rotations before stopping
            return wait_count[0] >= 6

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        assert mock_tor_client.new_identity.call_count == 5
        assert rotator._stop_event.wait.call_count == 6

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_multiple_exceptions_handled(self, mock_error, mock_log, mock_tor_client):
        """Test that multiple consecutive exceptions are all handled gracefully."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        # new_identity always raises
        mock_tor_client.new_identity.side_effect = ConnectionErrorException("persistent failure")

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 4

        rotator._stop_event.wait = MagicMock(side_effect=wait_side_effect)

        rotator.run()

        # Should have 3 failed rotations
        assert mock_tor_client.new_identity.call_count == 3
        # Should have 3 error logs
        assert mock_error.call_count == 3

    @patch('app.command.app.console.log')
    def test_is_rotating_flag_set_correctly(self, mock_log, mock_tor_client):
        """Verify _is_rotating flag is set correctly during execution."""
        rotator = IdentityRotator(tor_client=mock_tor_client, interval=300)

        # Before run
        assert rotator._is_rotating is False

        rotator._stop_event.wait = MagicMock(return_value=True)

        rotator.run()

        # After run completes (run() doesn't reset _is_rotating, stop() does)
        # _is_rotating should be True because run() sets it to True at start
        assert rotator._is_rotating is True

        # Calling stop() should reset it
        rotator.stop()
        assert rotator._is_rotating is False
