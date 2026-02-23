"""Comprehensive unit tests for the SoldierThread class.

This module provides complete test coverage for the SoldierThread class including:
- Initialization and default state
- Attack method setup and parameter handling
- Run loop behavior and attack execution
- Exception handling with RequestException
- Active thread counter integration
- Monitor integration for result reporting
- Thread safety and concurrent behavior
- Edge cases and boundary conditions

All external dependencies (weapon, monitor, app.console) are mocked to ensure
isolated unit tests.
"""

import threading
import time
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from app.command import SoldierThread
from app.models import AttackResult
from app.net import RequestException


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_monitor():
    """Create mock Monitor with all required methods."""
    monitor = MagicMock()
    monitor.report_attack_result = MagicMock()
    monitor.increment_active_threads = MagicMock()
    monitor.decrement_active_threads = MagicMock()
    return monitor


@pytest.fixture
def mock_weapon():
    """Create mock weapon with attack method returning successful AttackResult."""
    weapon = MagicMock()
    weapon.attack.return_value = AttackResult(
        num_hits=1,
        http_status=200,
        bytes_sent=100,
        bytes_received=200,
        response_time_ms=50.0,
        errors=0
    )
    weapon.target = MagicMock()
    return weapon


@pytest.fixture
def soldier_thread(mock_monitor):
    """Create fresh SoldierThread instance with mocked monitor."""
    return SoldierThread(tid=1, monitor=mock_monitor)


# =============================================================================
# TestSoldierThreadInitialization
# =============================================================================

class TestSoldierThreadInitialization:
    """Test __init__ parameters and initial state."""

    def test_soldier_thread_initializes_with_id(self, mock_monitor):
        """Verify _id is set correctly."""
        soldier = SoldierThread(tid=42, monitor=mock_monitor)
        assert soldier._id == 42

    def test_soldier_thread_initializes_with_monitor(self, mock_monitor):
        """Verify _monitor is set correctly."""
        soldier = SoldierThread(tid=1, monitor=mock_monitor)
        assert soldier._monitor is mock_monitor

    def test_soldier_thread_initializes_with_empty_target_url(self, mock_monitor):
        """Verify _target_url starts empty."""
        soldier = SoldierThread(tid=1, monitor=mock_monitor)
        assert soldier._target_url == ''

    def test_soldier_thread_initializes_with_none_weapon(self, mock_monitor):
        """Verify _weapon starts as None."""
        soldier = SoldierThread(tid=1, monitor=mock_monitor)
        assert soldier._weapon is None

    def test_soldier_thread_initializes_with_is_attacking_false(self, mock_monitor):
        """Verify _is_attacking starts False."""
        soldier = SoldierThread(tid=1, monitor=mock_monitor)
        assert soldier._is_attacking is False

    def test_soldier_thread_inherits_from_threading_thread(self, mock_monitor):
        """Verify isinstance(soldier, threading.Thread)."""
        soldier = SoldierThread(tid=1, monitor=mock_monitor)
        assert isinstance(soldier, threading.Thread)


# =============================================================================
# TestSoldierThreadAttackMethod
# =============================================================================

class TestSoldierThreadAttackMethod:
    """Test attack() method setup behavior."""

    def test_attack_sets_target_url(self, soldier_thread, mock_weapon):
        """Verify _target_url is set from kwargs."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)
        assert soldier_thread._target_url == 'http://example.com'

    def test_attack_sets_weapon(self, soldier_thread, mock_weapon):
        """Verify _weapon is set from kwargs."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)
        assert soldier_thread._weapon is mock_weapon

    def test_attack_calls_weapon_target(self, soldier_thread, mock_weapon, mock_monitor):
        """Verify weapon.target() is called with target_url and monitor."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)
        mock_weapon.target.assert_called_once_with('http://example.com', monitor=mock_monitor)

    def test_attack_sets_is_attacking_true(self, soldier_thread, mock_weapon):
        """Verify _is_attacking becomes True."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)
        assert soldier_thread._is_attacking is True

    def test_attack_increments_active_threads(self, soldier_thread, mock_weapon, mock_monitor):
        """Verify monitor.increment_active_threads() is called."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)
        mock_monitor.increment_active_threads.assert_called_once()

    def test_attack_starts_thread(self, soldier_thread, mock_weapon):
        """Verify thread.start() is called."""
        with patch.object(soldier_thread, 'start') as mock_start:
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)
        mock_start.assert_called_once()


# =============================================================================
# TestSoldierThreadRunMethod
# =============================================================================

class TestSoldierThreadRunMethod:
    """Test run() method core loop behavior."""

    @patch('app.command.app.console.log')
    def test_run_calls_weapon_attack(self, mock_log, soldier_thread, mock_weapon):
        """Mock weapon.attack() returning AttackResult, verify it's called."""
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        # Stop after first iteration
        def stop_after_first(*args, **kwargs):
            soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = stop_after_first

        soldier_thread.run()

        mock_weapon.attack.assert_called()

    @patch('app.command.app.console.log')
    def test_run_reports_attack_result_to_monitor(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Verify monitor.report_attack_result(self, result) is called with correct AttackResult."""
        expected_result = AttackResult(num_hits=1, http_status=200, bytes_sent=100, bytes_received=200)
        mock_weapon.attack.return_value = expected_result
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        # Stop after first iteration
        def stop_after_call(*args, **kwargs):
            soldier_thread._is_attacking = False
            return expected_result

        mock_weapon.attack.side_effect = stop_after_call

        soldier_thread.run()

        mock_monitor.report_attack_result.assert_called_once()
        call_args = mock_monitor.report_attack_result.call_args
        assert call_args[0][0] is soldier_thread
        assert call_args[0][1] is expected_result

    @patch('app.command.app.console.log')
    def test_run_loops_while_is_attacking_true(self, mock_log, soldier_thread, mock_weapon):
        """Set _is_attacking to False after 3 iterations, verify weapon.attack() called 3 times."""
        call_count = [0]

        def count_calls(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 3:
                soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = count_calls
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        assert call_count[0] == 3
        assert mock_weapon.attack.call_count == 3

    @patch('app.command.app.console.log')
    def test_run_stops_when_is_attacking_false(self, mock_log, soldier_thread, mock_weapon):
        """Start with _is_attacking=True, set to False after 1 iteration, verify loop exits."""
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = stop_immediately

        soldier_thread.run()

        assert mock_weapon.attack.call_count == 1

    @patch('app.command.app.console.log')
    def test_run_logs_starting_message(self, mock_log, soldier_thread, mock_weapon):
        """Mock app.console.log, verify 'starting soldier thread #X' is logged."""
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = stop_immediately

        soldier_thread.run()

        mock_log.assert_any_call("starting soldier thread #1")

    @patch('app.command.app.console.log')
    def test_run_passes_self_to_report_attack_result(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Verify first argument to report_attack_result is the SoldierThread instance."""
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = stop_immediately

        soldier_thread.run()

        call_args = mock_monitor.report_attack_result.call_args
        assert call_args[0][0] is soldier_thread


# =============================================================================
# TestSoldierThreadExceptionHandling
# =============================================================================

class TestSoldierThreadExceptionHandling:
    """Test exception handling in run() method."""

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_requestexception_creates_error_attack_result(self, mock_error, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Mock weapon.attack() to raise RequestException, verify error AttackResult with errors=1, num_hits=0, http_status=None."""
        mock_weapon.attack.side_effect = RequestException("connection failed")
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        # Stop after exception
        original_is_attacking = soldier_thread._is_attacking

        def raise_once(*args, **kwargs):
            soldier_thread._is_attacking = False
            raise RequestException("connection failed")

        mock_weapon.attack.side_effect = raise_once

        soldier_thread.run()

        # Verify error result was reported
        mock_monitor.report_attack_result.assert_called()
        call_args = mock_monitor.report_attack_result.call_args
        error_result = call_args[0][1]
        assert error_result.errors == 1
        assert error_result.num_hits == 0
        assert error_result.http_status is None
        assert error_result.bytes_sent == 0
        assert error_result.bytes_received == 0

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_requestexception_logs_error_message(self, mock_error, mock_log, soldier_thread, mock_weapon):
        """Mock app.console.error, verify error message is logged."""
        mock_weapon.attack.side_effect = RequestException("connection failed")
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def raise_once(*args, **kwargs):
            soldier_thread._is_attacking = False
            raise RequestException("connection failed")

        mock_weapon.attack.side_effect = raise_once

        soldier_thread.run()

        mock_error.assert_called_with("connection failed")

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_requestexception_reports_error_result_to_monitor(self, mock_error, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Verify monitor.report_attack_result() is called with error AttackResult."""
        mock_weapon.attack.side_effect = RequestException("connection failed")
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def raise_once(*args, **kwargs):
            soldier_thread._is_attacking = False
            raise RequestException("connection failed")

        mock_weapon.attack.side_effect = raise_once

        soldier_thread.run()

        mock_monitor.report_attack_result.assert_called()
        call_args = mock_monitor.report_attack_result.call_args
        error_result = call_args[0][1]
        assert isinstance(error_result, AttackResult)
        assert error_result.errors == 1

    @patch('app.command.app.console.log')
    @patch('app.command.app.console.error')
    def test_requestexception_continues_loop(self, mock_error, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Raise RequestException on first call, return success on second, verify loop continues."""
        call_count = [0]

        def mixed_behavior(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RequestException("connection failed")
            elif call_count[0] == 2:
                soldier_thread._is_attacking = False
                return AttackResult(num_hits=1, http_status=200)
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = mixed_behavior
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        # Should have 2 calls: first raises exception, second succeeds
        assert call_count[0] == 2
        # Should report twice: once for error, once for success
        assert mock_monitor.report_attack_result.call_count == 2

    @patch('app.command.app.console.log')
    def test_generic_exception_does_not_create_error_result(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Generic exceptions should propagate (not caught like RequestException)."""
        mock_weapon.attack.side_effect = ValueError("unexpected error")
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        with pytest.raises(ValueError, match="unexpected error"):
            soldier_thread.run()


# =============================================================================
# TestSoldierThreadLifecycle
# =============================================================================

class TestSoldierThreadLifecycle:
    """Test thread lifecycle methods."""

    def test_hold_fire_sets_is_attacking_false(self, soldier_thread):
        """Verify _is_attacking becomes False."""
        soldier_thread._is_attacking = True
        with patch('app.command.app.console.log'):
            soldier_thread.hold_fire()
        assert soldier_thread._is_attacking is False

    @patch('app.command.app.console.log')
    def test_hold_fire_logs_stopping_message(self, mock_log, soldier_thread):
        """Mock app.console.log, verify 'stopping soldier thread #X' is logged."""
        soldier_thread._id = 5
        soldier_thread.hold_fire()
        mock_log.assert_called_with("stopping soldier thread #5")

    @patch('app.command.app.console.log')
    def test_wait_done_calls_join_when_thread_alive(self, mock_log, soldier_thread):
        """Mock is_alive() to return True, verify join() is called."""
        with patch.object(soldier_thread, 'is_alive', return_value=True):
            with patch.object(soldier_thread, 'join') as mock_join:
                soldier_thread.wait_done()
        mock_join.assert_called_once()

    @patch('app.command.app.console.log')
    def test_wait_done_does_not_call_join_when_thread_not_alive(self, mock_log, soldier_thread):
        """Mock is_alive() to return False, verify join() not called."""
        with patch.object(soldier_thread, 'is_alive', return_value=False):
            with patch.object(soldier_thread, 'join') as mock_join:
                soldier_thread.wait_done()
        mock_join.assert_not_called()

    @patch('app.command.app.console.log')
    def test_wait_done_logs_waiting_message(self, mock_log, soldier_thread):
        """Mock app.console.log, verify 'waiting for soldier thread #X' is logged."""
        soldier_thread._id = 7
        with patch.object(soldier_thread, 'is_alive', return_value=False):
            soldier_thread.wait_done()
        mock_log.assert_called_with("waiting for soldier thread #7")


# =============================================================================
# TestSoldierThreadActiveThreadCounters
# =============================================================================

class TestSoldierThreadActiveThreadCounters:
    """Test active thread counter integration."""

    @patch('app.command.app.console.log')
    def test_run_decrements_active_threads_on_normal_exit(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Verify monitor.decrement_active_threads() is called when run() completes normally."""
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = stop_immediately

        soldier_thread.run()

        mock_monitor.decrement_active_threads.assert_called_once()

    @patch('app.command.app.console.log')
    def test_run_decrements_active_threads_on_exception(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Raise exception in weapon.attack(), verify decrement_active_threads() still called (finally block)."""
        mock_weapon.attack.side_effect = ValueError("unexpected error")
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        try:
            soldier_thread.run()
        except ValueError:
            pass

        mock_monitor.decrement_active_threads.assert_called_once()

    @patch('app.command.app.console.log')
    def test_run_decrements_active_threads_exactly_once(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Verify decrement is called exactly once even with multiple loop iterations."""
        call_count = [0]

        def count_calls(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 5:
                soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = count_calls
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        assert call_count[0] == 5
        mock_monitor.decrement_active_threads.assert_called_once()

    def test_increment_and_decrement_pairing(self, soldier_thread, mock_weapon, mock_monitor):
        """Verify increment is called in attack(), decrement in run() finally block."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(target_url='http://example.com', weapon=mock_weapon)

        mock_monitor.increment_active_threads.assert_called_once()

        # Now simulate run() with immediate stop
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200)

        mock_weapon.attack.side_effect = stop_immediately

        with patch('app.command.app.console.log'):
            soldier_thread.run()

        mock_monitor.decrement_active_threads.assert_called_once()


# =============================================================================
# TestSoldierThreadMonitorIntegration
# =============================================================================

class TestSoldierThreadMonitorIntegration:
    """Test monitor integration without network calls."""

    @patch('app.command.app.console.log')
    def test_successful_attack_result_reported(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Create AttackResult with num_hits=1, http_status=200, bytes_sent=100, bytes_received=200, response_time_ms=50.0, errors=0, verify reported correctly."""
        expected_result = AttackResult(
            num_hits=1,
            http_status=200,
            bytes_sent=100,
            bytes_received=200,
            response_time_ms=50.0,
            errors=0
        )
        mock_weapon.attack.return_value = expected_result
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return expected_result

        mock_weapon.attack.side_effect = stop_immediately

        soldier_thread.run()

        mock_monitor.report_attack_result.assert_called_once_with(soldier_thread, expected_result)

    @patch('app.command.app.console.log')
    def test_multiple_attack_results_reported(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Loop 5 times, verify monitor.report_attack_result() called 5 times with different results."""
        call_count = [0]
        results = []

        def generate_results(*args, **kwargs):
            call_count[0] += 1
            result = AttackResult(num_hits=call_count[0], http_status=200 + call_count[0])
            results.append(result)
            if call_count[0] >= 5:
                soldier_thread._is_attacking = False
            return result

        mock_weapon.attack.side_effect = generate_results
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        assert mock_monitor.report_attack_result.call_count == 5
        for i, result in enumerate(results):
            mock_monitor.report_attack_result.assert_any_call(soldier_thread, result)

    @patch('app.command.app.console.log')
    def test_attack_result_with_various_http_statuses(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Test reporting results with http_status 200, 404, 500, None."""
        statuses = [200, 404, 500, None]
        call_count = [0]

        def generate_with_status(*args, **kwargs):
            status = statuses[call_count[0] % len(statuses)]
            call_count[0] += 1
            if call_count[0] >= len(statuses):
                soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=status)

        mock_weapon.attack.side_effect = generate_with_status
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        assert mock_monitor.report_attack_result.call_count == 4

    @patch('app.command.app.console.log')
    def test_attack_result_with_various_byte_counts(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Test reporting results with different bytes_sent/bytes_received values."""
        byte_values = [
            (0, 0),
            (100, 200),
            (1000, 5000),
            (999999, 888888)
        ]
        call_count = [0]

        def generate_with_bytes(*args, **kwargs):
            sent, received = byte_values[call_count[0] % len(byte_values)]
            call_count[0] += 1
            if call_count[0] >= len(byte_values):
                soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200, bytes_sent=sent, bytes_received=received)

        mock_weapon.attack.side_effect = generate_with_bytes
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        assert mock_monitor.report_attack_result.call_count == 4

        # Verify byte counts in reported results
        for i, (sent, received) in enumerate(byte_values):
            call_args = mock_monitor.report_attack_result.call_args_list[i]
            result = call_args[0][1]
            assert result.bytes_sent == sent
            assert result.bytes_received == received

    @patch('app.command.app.console.log')
    def test_attack_result_with_response_times(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Test reporting results with response_time_ms values (None, 0.5, 100.0, 5000.0)."""
        response_times = [None, 0.5, 100.0, 5000.0]
        call_count = [0]

        def generate_with_time(*args, **kwargs):
            response_time = response_times[call_count[0] % len(response_times)]
            call_count[0] += 1
            if call_count[0] >= len(response_times):
                soldier_thread._is_attacking = False
            return AttackResult(num_hits=1, http_status=200, response_time_ms=response_time)

        mock_weapon.attack.side_effect = generate_with_time
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        soldier_thread.run()

        assert mock_monitor.report_attack_result.call_count == 4

        # Verify response times in reported results
        for i, response_time in enumerate(response_times):
            call_args = mock_monitor.report_attack_result.call_args_list[i]
            result = call_args[0][1]
            assert result.response_time_ms == response_time


# =============================================================================
# TestSoldierThreadConcurrency
# =============================================================================

class TestSoldierThreadConcurrency:
    """Test thread safety and concurrent behavior."""

    @patch('app.command.app.console.log')
    def test_multiple_soldier_threads_run_concurrently(self, mock_log, mock_monitor):
        """Create 3 SoldierThread instances, start all, verify all run concurrently."""
        threads = []
        run_flags = []

        for i in range(3):
            soldier = SoldierThread(tid=i, monitor=mock_monitor)
            mock_weapon = MagicMock()
            mock_weapon.attack.return_value = AttackResult(num_hits=1, http_status=200)
            mock_weapon.target = MagicMock()

            soldier._weapon = mock_weapon
            run_flags.append({'ran': False})

            # Create wrapper to track execution
            def make_run(soldier, flag):
                original_run = soldier.run
                def tracked_run():
                    flag['ran'] = True
                    original_run()
                return tracked_run

            soldier.run = make_run(soldier, run_flags[i])
            threads.append((soldier, mock_weapon))

        # Start all threads
        for soldier, _ in threads:
            with patch.object(soldier, 'start'):
                soldier.attack(target_url='http://example.com', weapon=threads[soldier._id][1])
            soldier._is_attacking = True

        # Stop them immediately and run synchronously for test
        for soldier, mock_weapon in threads:
            def stop_immediately(*args, **kwargs):
                soldier._is_attacking = False
                return AttackResult(num_hits=1, http_status=200)
            mock_weapon.attack.side_effect = stop_immediately
            soldier.run()

        # Verify all threads ran
        for flag in run_flags:
            assert flag['ran'] is True

    @patch('app.command.app.console.log')
    def test_hold_fire_stops_all_threads(self, mock_log, mock_monitor):
        """Start multiple threads, call hold_fire() on all, verify all stop."""
        soldiers = []

        for i in range(3):
            soldier = SoldierThread(tid=i, monitor=mock_monitor)
            mock_weapon = MagicMock()
            mock_weapon.attack.return_value = AttackResult(num_hits=1, http_status=200)
            mock_weapon.target = MagicMock()

            soldier._weapon = mock_weapon
            soldier._is_attacking = True
            soldiers.append(soldier)

        # Call hold_fire on all
        for soldier in soldiers:
            soldier.hold_fire()

        # Verify all stopped
        for soldier in soldiers:
            assert soldier._is_attacking is False

    @patch('app.command.app.console.log')
    def test_monitor_receives_results_from_multiple_threads(self, mock_log, mock_monitor):
        """Start 3 threads, verify monitor receives results from all 3."""
        soldiers = []

        for i in range(3):
            soldier = SoldierThread(tid=i, monitor=mock_monitor)
            mock_weapon = MagicMock()
            mock_weapon.attack.return_value = AttackResult(num_hits=1, http_status=200, bytes_sent=100 * i)
            mock_weapon.target = MagicMock()

            soldier._weapon = mock_weapon
            soldier._is_attacking = True

            def stop_immediately(*args, soldier=soldier, **kwargs):
                soldier._is_attacking = False
                return AttackResult(num_hits=1, http_status=200)

            mock_weapon.attack.side_effect = stop_immediately
            soldiers.append(soldier)

        # Run all soldiers
        for soldier in soldiers:
            soldier.run()

        # Verify monitor received 3 calls
        assert mock_monitor.report_attack_result.call_count == 3


# =============================================================================
# TestSoldierThreadEdgeCases
# =============================================================================

class TestSoldierThreadEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_attack_with_missing_target_url_kwarg(self, soldier_thread, mock_weapon):
        """Call attack() without target_url, verify _target_url is None."""
        with patch.object(soldier_thread, 'start'):
            soldier_thread.attack(weapon=mock_weapon)
        assert soldier_thread._target_url is None

    def test_attack_with_missing_weapon_kwarg(self, soldier_thread):
        """Call attack() without weapon, verify AttributeError is raised."""
        with patch.object(soldier_thread, 'start'):
            with pytest.raises(AttributeError):
                soldier_thread.attack(target_url='http://example.com')

    @patch('app.command.app.console.log')
    def test_run_with_none_weapon(self, mock_log, soldier_thread, mock_monitor):
        """Set _weapon to None, _is_attacking to True, verify AttributeError or graceful handling."""
        soldier_thread._weapon = None
        soldier_thread._is_attacking = True

        # Should raise AttributeError when trying to call None.attack()
        with pytest.raises(AttributeError):
            soldier_thread.run()

    @patch('app.command.app.console.log')
    def test_weapon_attack_returns_none(self, mock_log, soldier_thread, mock_weapon, mock_monitor):
        """Mock weapon.attack() to return None, verify monitor is called with None."""
        mock_weapon.attack.return_value = None
        soldier_thread._weapon = mock_weapon
        soldier_thread._is_attacking = True

        def stop_immediately(*args, **kwargs):
            soldier_thread._is_attacking = False
            return None

        mock_weapon.attack.side_effect = stop_immediately

        # Run should complete normally and pass None to the monitor
        soldier_thread.run()

        # Verify monitor was called with None as the result
        mock_monitor.report_attack_result.assert_called_once_with(soldier_thread, None)

    def test_rapid_hold_fire_calls(self, soldier_thread):
        """Call hold_fire() multiple times rapidly, verify no issues."""
        soldier_thread._is_attacking = True

        with patch('app.command.app.console.log'):
            for _ in range(10):
                soldier_thread.hold_fire()

        # Should still be False, no errors raised
        assert soldier_thread._is_attacking is False
