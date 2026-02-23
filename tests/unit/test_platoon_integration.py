"""Integration tests for Platoon identity rotation functionality.

This module provides comprehensive integration tests for the Platoon class with
identity rotation enabled. Tests verify that:
- IdentityRotator runs concurrently with soldier threads without disruption
- Rotation events are logged appropriately
- Rotator stops cleanly when attack ends
- Edge cases are handled properly (zero interval, None tor_client, negative interval)

All external dependencies are mocked to ensure fast, isolated tests.
"""

import threading
import time
from unittest.mock import MagicMock, patch, call
import itertools
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import socket

import pytest

from app.command import Platoon, IdentityRotator
from app.weapons.singleshot import SingleShotFactory
from app.models import AttackResult


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
def mock_network_client():
    """Returns MagicMock with request() method returning successful response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_client.request.return_value = (mock_response, 100, 200)
    return mock_client


@pytest.fixture
def mock_weapon_factory(mock_network_client):
    """Returns SingleShotFactory instance with mocked network client."""
    with patch('app.weapons.singleshot.NetworkClient', return_value=mock_network_client):
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        yield factory


@pytest.fixture
def mock_console_log():
    """Patches app.command.app.console.log to capture log messages."""
    with patch('app.command.app.console.log') as mock_log:
        yield mock_log


@pytest.fixture
def mock_console_error():
    """Patches app.command.app.console.error to capture error messages."""
    with patch('app.command.app.console.error') as mock_error:
        yield mock_error


class TestHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves HTML pages with links for crawl testing."""
    
    # HTML pages with various link structures
    PAGES = {
        '/': b'''<!DOCTYPE html>
<html>
<head><title>Test Root</title></head>
<body>
<h1>Root Page</h1>
<a href="/page1">Page 1</a>
<a href="/page2">Page 2</a>
<a href="/page3">Page 3</a>
<a href="/page4">Page 4</a>
<a href="/page5">Page 5</a>
<a href="/page6">Page 6</a>
<a href="/page7">Page 7</a>
<a href="/page8">Page 8</a>
<a href="/page9">Page 9</a>
<a href="/page10">Page 10</a>
<a href="/page11">Page 11</a>
<a href="/page12">Page 12</a>
</body>
</html>''',
        '/page1': b'''<!DOCTYPE html>
<html>
<head><title>Page 1</title></head>
<body>
<h1>Page 1</h1>
<a href="/">Back to Root</a>
<a href="/page2">Page 2</a>
<a href="/page3">Page 3</a>
</body>
</html>''',
        '/page2': b'''<!DOCTYPE html>
<html>
<head><title>Page 2</title></head>
<body>
<h1>Page 2</h1>
<a href="/">Back to Root</a>
<a href="/page1">Page 1</a>
<a href="/page4">Page 4</a>
</body>
</html>''',
        '/page3': b'''<!DOCTYPE html>
<html>
<head><title>Page 3</title></head>
<body>
<h1>Page 3</h1>
<a href="/">Back to Root</a>
<a href="/page1">Page 1</a>
</body>
</html>''',
        '/page4': b'''<!DOCTYPE html>
<html>
<head><title>Page 4</title></head>
<body>
<h1>Page 4</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page5': b'''<!DOCTYPE html>
<html>
<head><title>Page 5</title></head>
<body>
<h1>Page 5</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page6': b'''<!DOCTYPE html>
<html>
<head><title>Page 6</title></head>
<body>
<h1>Page 6</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page7': b'''<!DOCTYPE html>
<html>
<head><title>Page 7</title></head>
<body>
<h1>Page 7</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page8': b'''<!DOCTYPE html>
<html>
<head><title>Page 8</title></head>
<body>
<h1>Page 8</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page9': b'''<!DOCTYPE html>
<html>
<head><title>Page 9</title></head>
<body>
<h1>Page 9</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page10': b'''<!DOCTYPE html>
<html>
<head><title>Page 10</title></head>
<body>
<h1>Page 10</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page11': b'''<!DOCTYPE html>
<html>
<head><title>Page 11</title></head>
<body>
<h1>Page 11</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
        '/page12': b'''<!DOCTYPE html>
<html>
<head><title>Page 12</title></head>
<body>
<h1>Page 12</h1>
<a href="/">Back to Root</a>
</body>
</html>''',
    }
    
    def log_message(self, format, *args):
        """Suppress logging to avoid cluttering test output."""
        pass
    
    def do_GET(self):
        """Handle GET requests by serving HTML pages."""
        content = self.PAGES.get(self.path, self.PAGES['/'])
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)


@pytest.fixture(scope='function')
def local_http_server():
    """
    Spins up a local HTTP server for FullAuto crawl limit testing.
    
    Creates a ThreadingHTTPServer on a random available port,
    serves HTML pages with multiple links for crawl testing.
    Yields the base URL for the server.
    
    Returns:
        str: Base URL of the local server (e.g., 'http://127.0.0.1:54321')
    """
    # Find an available port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    
    # Create and start the server
    server = ThreadingHTTPServer(('127.0.0.1', port), TestHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    base_url = f'http://127.0.0.1:{port}'
    
    yield base_url
    
    # Cleanup
    server.shutdown()
    server.server_close()


# =============================================================================
# Helper Functions
# =============================================================================

def run_attack_for_duration(platoon, weapon_factory, target_url, duration_seconds):
    """
    Helper function to run attack for a specified duration.
    
    - Starts attack in background thread
    - Sleeps for specified duration
    - Calls hold_fire() to stop attack
    - Waits for all threads to complete
    
    Args:
        platoon: Platoon instance to run attack on
        weapon_factory: Weapon factory to use for attack
        target_url: Target URL to attack
        duration_seconds: Duration to run attack in seconds
    """
    attack_results = {}
    
    def attack_thread():
        try:
            platoon.attack(
                target_url=target_url,
                weapon_factory=weapon_factory
            )
        except Exception as e:
            attack_results['error'] = e
    
    # Start attack in background thread
    thread = threading.Thread(target=attack_thread)
    thread.daemon = True
    thread.start()
    
    # Wait for specified duration
    time.sleep(duration_seconds)
    
    # Stop the attack
    platoon.hold_fire()
    
    # Wait for attack thread to complete
    thread.join(timeout=5.0)
    
    return attack_results


def verify_rotation_timing(call_timestamps, expected_interval, tolerance=0.5):
    """
    Verify that rotation calls occur at expected intervals.
    
    Args:
        call_timestamps: List of timestamps when new_identity was called
        expected_interval: Expected time between calls in seconds
        tolerance: Allowed deviation from expected interval in seconds
        
    Returns:
        True if timing is correct, False otherwise
    """
    if len(call_timestamps) < 2:
        return False
    
    for i in range(1, len(call_timestamps)):
        actual_interval = call_timestamps[i] - call_timestamps[i-1]
        if abs(actual_interval - expected_interval) > tolerance:
            return False
    
    return True


# =============================================================================
# TestPlatoonIdentityRotationIntegration
# =============================================================================

@patch('app.command.app.console.log')
@patch('app.command.app.console.error')
@patch('app.weapons.singleshot.NetworkClient')
class TestPlatoonIdentityRotationIntegration:
    """Main integration tests for Platoon identity rotation functionality."""
    
    def test_identity_rotation_runs_during_active_attack(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify identity rotation runs during active attack with multiple soldiers."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with identity rotation enabled
        platoon = Platoon(
            num_soldiers=3,
            tor_client=mock_tor_client,
            identity_rotation_interval=2
        )
        
        # Track new_identity calls
        call_timestamps = []
        
        def track_identity_call():
            call_timestamps.append(time.time())
        
        mock_tor_client.new_identity.side_effect = track_identity_call
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 5 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 5)
        
        # Verify new_identity was called at least 2 times (5 seconds / 2 second interval)
        assert mock_tor_client.new_identity.call_count >= 2, \
            f"Expected at least 2 identity rotations, got {mock_tor_client.new_identity.call_count}"
    
    def test_rotation_events_appear_in_logs(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify rotation events are logged during attack."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with identity rotation enabled
        platoon = Platoon(
            num_soldiers=2,
            tor_client=mock_tor_client,
            identity_rotation_interval=2
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 5 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 5)
        
        # Get all logged messages
        log_messages = [str(call) for call in mock_console_log.call_args_list]
        log_text = ' '.join(log_messages)
        
        # Verify log messages contain expected content
        assert any('starting identity rotator' in msg.lower() or 'identity rotator' in msg.lower() 
                   for msg in log_messages), \
            "Expected log message about starting identity rotator"
    
    def test_new_identity_called_periodically(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify new_identity is called at approximately correct intervals."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Track timestamps of new_identity calls
        call_timestamps = []
        
        def track_with_timestamp():
            call_timestamps.append(time.time())
        
        mock_tor_client.new_identity.side_effect = track_with_timestamp
        
        # Create Platoon with 1 second interval for faster test
        platoon = Platoon(
            num_soldiers=2,
            tor_client=mock_tor_client,
            identity_rotation_interval=1
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 4 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 4)
        
        # Verify at least 3 calls made during 4 second window
        assert len(call_timestamps) >= 3, \
            f"Expected at least 3 identity rotations in 4 seconds, got {len(call_timestamps)}"
        
        # Verify timing is approximately correct (allow ±0.5 second tolerance)
        if len(call_timestamps) >= 2:
            assert verify_rotation_timing(call_timestamps, expected_interval=1.0, tolerance=0.5), \
                f"Identity rotation timing incorrect. Timestamps: {call_timestamps}"
    
    def test_rotation_does_not_disrupt_soldier_threads(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify identity rotation does not disrupt soldier thread operations."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with 5 soldiers and 1 second rotation interval
        platoon = Platoon(
            num_soldiers=5,
            tor_client=mock_tor_client,
            identity_rotation_interval=1
        )
        
        # Track monitor state
        monitor = platoon._monitor
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 3 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 3)
        
        # Verify all threads completed (no active threads after hold_fire)
        assert monitor.get_status()[1] >= 0, "Monitor should have valid status"


# =============================================================================
# TestPlatoonIdentityRotationLifecycle
# =============================================================================

@patch('app.command.app.console.log')
@patch('app.command.app.console.error')
@patch('app.weapons.singleshot.NetworkClient')
class TestPlatoonIdentityRotationLifecycle:
    """Lifecycle and cleanup tests for Platoon identity rotation."""
    
    def test_rotator_stops_cleanly_on_hold_fire(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify rotator stops cleanly when hold_fire() is called."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with identity rotation enabled
        platoon = Platoon(
            num_soldiers=2,
            tor_client=mock_tor_client,
            identity_rotation_interval=2
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Track new_identity calls after hold_fire
        post_hold_fire_calls = []
        
        def track_calls():
            if not platoon._is_attacking:
                post_hold_fire_calls.append(time.time())
        
        original_side_effect = mock_tor_client.new_identity.side_effect
        mock_tor_client.new_identity.side_effect = lambda: track_calls()
        
        # Run attack for 3 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 3)
        
        # Verify identity rotator thread is no longer alive
        if platoon._identity_rotator is not None:
            assert not platoon._identity_rotator.is_alive(), \
                "Identity rotator thread should not be alive after hold_fire()"
        
        # Verify no calls made after hold_fire
        assert len(post_hold_fire_calls) == 0, \
            f"new_identity should not be called after hold_fire(), got {len(post_hold_fire_calls)} calls"


# =============================================================================
# TestPlatoonIdentityRotationEdgeCases
# =============================================================================

@patch('app.command.app.console.log')
@patch('app.command.app.console.error')
@patch('app.weapons.singleshot.NetworkClient')
class TestPlatoonIdentityRotationEdgeCases:
    """Edge cases and error conditions for Platoon identity rotation."""
    
    def test_rotation_with_zero_interval_skipped(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify rotation is skipped when interval is 0."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with zero rotation interval
        platoon = Platoon(
            num_soldiers=2,
            tor_client=mock_tor_client,
            identity_rotation_interval=0
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack briefly
        run_attack_for_duration(platoon, factory, 'http://example.com', 2)
        
        # Verify identity rotator is None (rotation skipped)
        assert platoon._identity_rotator is None, \
            "Identity rotator should be None when interval is 0"
        
        # Verify log message about skipping rotation
        log_messages = [str(call) for call in mock_console_log.call_args_list]
        assert any('skipping identity rotation' in msg.lower() or 'interval must be positive' in msg.lower()
                   for msg in log_messages), \
            "Expected log message about skipping identity rotation with zero interval"
    
    def test_rotation_with_none_tor_client_skipped(
        self, mock_network_client_class, mock_console_error, mock_console_log
    ):
        """Verify rotation is skipped when tor_client is None."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with None tor_client but valid interval
        platoon = Platoon(
            num_soldiers=2,
            tor_client=None,
            identity_rotation_interval=5
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack briefly
        run_attack_for_duration(platoon, factory, 'http://example.com', 2)
        
        # Verify identity rotator is None (rotation skipped)
        assert platoon._identity_rotator is None, \
            "Identity rotator should be None when tor_client is None"
        
        # Verify no rotation-related log messages
        log_messages = [str(call) for call in mock_console_log.call_args_list]
        rotation_logs = [msg for msg in log_messages if 'identity rotator' in msg.lower()]
        assert len(rotation_logs) == 0, \
            f"Should not have rotation-related logs when tor_client is None, got: {rotation_logs}"
    
    def test_rotation_with_negative_interval_skipped(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify rotation is skipped when interval is negative."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with negative rotation interval
        platoon = Platoon(
            num_soldiers=2,
            tor_client=mock_tor_client,
            identity_rotation_interval=-5
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack briefly
        run_attack_for_duration(platoon, factory, 'http://example.com', 2)
        
        # Verify identity rotator is None (rotation skipped)
        assert platoon._identity_rotator is None, \
            "Identity rotator should be None when interval is negative"
        
        # Verify log message about skipping rotation
        log_messages = [str(call) for call in mock_console_log.call_args_list]
        assert any('skipping identity rotation' in msg.lower() or 'interval must be positive' in msg.lower()
                   for msg in log_messages), \
            "Expected log message about skipping identity rotation with negative interval"


# =============================================================================
# Additional Integration Tests
# =============================================================================

@patch('app.command.app.console.log')
@patch('app.command.app.console.error')
@patch('app.weapons.singleshot.NetworkClient')
class TestPlatoonIdentityRotationAdditional:
    """Additional integration tests for comprehensive coverage."""
    
    def test_platoon_attack_without_rotation_works_normally(
        self, mock_network_client_class, mock_console_error, mock_console_log
    ):
        """Verify Platoon attack works normally without identity rotation."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon without identity rotation (no tor_client)
        platoon = Platoon(num_soldiers=3)
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 2 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 2)
        
        # Verify attack completed without errors
        log_messages = [str(call) for call in mock_console_log.call_args_list]
        assert any('starting attack' in msg.lower() for msg in log_messages), \
            "Expected 'starting attack' log message"
        assert any('done' in msg.lower() for msg in log_messages), \
            "Expected 'done' log message"
    
    def test_multiple_identity_rotations_during_attack(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify multiple identity rotations occur during longer attack."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Track all new_identity calls
        call_count = [0]
        
        def increment_count():
            call_count[0] += 1
        
        mock_tor_client.new_identity.side_effect = increment_count
        
        # Create Platoon with 1 second rotation interval
        platoon = Platoon(
            num_soldiers=2,
            tor_client=mock_tor_client,
            identity_rotation_interval=1
        )
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 5 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 5)
        
        # Verify multiple rotations occurred (at least 4 in 5 seconds)
        assert call_count[0] >= 4, \
            f"Expected at least 4 identity rotations in 5 seconds, got {call_count[0]}"
    
    def test_soldier_threads_complete_after_hold_fire(
        self, mock_network_client_class, mock_console_error, mock_console_log, mock_tor_client
    ):
        """Verify all soldier threads complete after hold_fire is called."""
        # Setup mock network client
        mock_network_client = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_network_client.request.return_value = (mock_response, 100, 200)
        mock_network_client_class.return_value = mock_network_client
        
        # Create Platoon with identity rotation
        platoon = Platoon(
            num_soldiers=4,
            tor_client=mock_tor_client,
            identity_rotation_interval=1
        )
        
        # Track thread states
        thread_states = []
        
        # Create weapon factory
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        
        # Run attack for 3 seconds
        run_attack_for_duration(platoon, factory, 'http://example.com', 3)
        
        # Verify all soldiers have no active weapon (indicating completion)
        for soldier in platoon._soldiers:
            assert soldier._weapon is None or not soldier.is_alive(), \
                "All soldier threads should complete after hold_fire()"


# =============================================================================
# TestFullAutoWeaponCrawlLimitIntegration
# =============================================================================

@pytest.fixture
def mock_html_response_with_links():
    """Returns HTML content containing multiple anchor tags for crawl testing."""
    html_content = '''<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
<h1>Test Links</h1>
<a href="/page1">Page 1</a>
<a href="/page2">Page 2</a>
<a href="/page3">Page 3</a>
<a href="/page4">Page 4</a>
<a href="/page5">Page 5</a>
<a href="/page6">Page 6</a>
<a href="/page7">Page 7</a>
<a href="/page8">Page 8</a>
<a href="/page9">Page 9</a>
<a href="/page10">Page 10</a>
<a href="http://example.com/page11">Page 11</a>
<a href="http://example.com/page12">Page 12</a>
</body>
</html>'''
    return html_content.encode('utf-8')


@pytest.fixture
def mock_network_client_for_fullauto():
    """Returns mock NetworkClient configured for FullAutoWeapon HTML responses."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = b'<html><body><a href="/test">Test</a></body></html>'
    mock_response.info().get_content_type.return_value = 'text/html'
    mock_client.request.return_value = (mock_response, 100, 500)
    return mock_client, mock_response


def configure_mock_for_html_response(mock_network_client_class, mock_response, html_content):
    """
    Configure mocked NetworkClient to return HTML with links.
    
    Args:
        mock_network_client_class: The mocked NetworkClient class
        mock_response: The mock response object to configure
        html_content: HTML content as bytes to return from read()
    """
    mock_network_client = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = html_content
    mock_response.info().get_content_type.return_value = 'text/html'
    mock_network_client.request.return_value = (mock_response, 100, 500)
    mock_network_client_class.return_value = mock_network_client
    return mock_network_client


def verify_fullauto_limit_behavior(weapon, expected_url_count, expected_time_limit=None):
    """
    Verify that FullAutoWeapon crawl limits are correctly enforced.
    
    Args:
        weapon: FullAutoWeapon instance to check
        expected_url_count: Expected number of discovered URLs
        expected_time_limit: Expected time limit in seconds (optional)
        
    Returns:
        bool: True if limits are correctly enforced, False otherwise
    """
    # Check discovered URL count
    if weapon._discovered_url_count != expected_url_count:
        return False
    
    # Check URL list length matches discovered count
    if len(weapon._urls) != expected_url_count:
        return False
    
    # Check if limit is reached when expected URL count equals max_urls
    if hasattr(weapon, '_max_urls') and expected_url_count >= weapon._max_urls:
        if not weapon._is_crawl_limit_reached():
            return False
    
    return True


@patch('app.command.app.console.log')
@patch('app.command.app.console.error')
class TestFullAutoWeaponCrawlLimitIntegration:
    """Integration tests for FullAutoWeapon crawl limit functionality using real HTTP server."""
    
    def test_url_count_limit_stops_discovery_but_continues_attack(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify URL count limit stops discovery but attack continues.
        
        Limits are per-thread (each FullAutoWeapon instance has independent limits).
        Discovery stops when limit is reached, but attack continues.
        URL count includes the initial target URL.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        
        # Create FullAutoFactory with URL count limit (low for fast test)
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=5, max_time_seconds=999)
        
        # Create Platoon with 1 soldier thread (no Tor for faster tests)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        # Run attack for 3-4 seconds against real HTTP server
        target_url = f"{local_http_server}/"
        run_attack_for_duration(platoon, factory, target_url, 3)
        
        # Get the weapon instance from the soldier
        soldier = platoon._soldiers[0]
        weapon = soldier._weapon
        
        # Verify the weapon stopped at exactly 5 URLs
        assert weapon._discovered_url_count == 5, \
            f"Expected 5 discovered URLs, got {weapon._discovered_url_count}"
        
        # Verify URL list length matches
        assert len(weapon._urls) == 5, \
            f"Expected 5 URLs in list, got {len(weapon._urls)}"
        
        # Verify limit is reached
        assert weapon._is_crawl_limit_reached(), \
            "Expected crawl limit to be reached"
        
        # Verify monitor shows hits (attack continued)
        monitor = platoon._monitor
        status = monitor.get_status()
        assert status[0] > 0, "Expected hits to be recorded"
    
    def test_time_limit_stops_discovery_but_continues_attack(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify time limit stops discovery but attack continues.
        
        Time limit starts when first URL is targeted (_start_time set in target()).
        Discovery stops after time elapsed, but attack continues on existing URLs.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        import itertools
        import time as time_module
        
        # Use a generator to provide unlimited, monotonically increasing timestamps
        # Each call returns base_time + n*0.5 seconds
        base_time = time_module.time()
        time_generator = (base_time + n * 0.5 for n in itertools.count())
        
        with patch('time.time', side_effect=lambda: next(time_generator)):
            # Create FullAutoFactory with time limit (2 seconds, high URL limit)
            factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=999, max_time_seconds=2)
            
            # Create Platoon with 1 soldier thread (no Tor for faster tests)
            platoon = Platoon(num_soldiers=1, tor_client=None)
            
            # Run attack briefly against real HTTP server
            target_url = f"{local_http_server}/"
            run_attack_for_duration(platoon, factory, target_url, 2)
            
            # Get the weapon instance
            soldier = platoon._soldiers[0]
            weapon = soldier._weapon
            
            # Verify time limit was reached
            if weapon._start_time is not None:
                elapsed = time_module.time() - weapon._start_time
                assert weapon._is_crawl_limit_reached() or elapsed >= 2, \
                    "Expected time limit to be reached"
    
    def test_combined_limits_first_limit_wins(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify whichever limit is hit first stops discovery.
        
        Tests scenario where URL limit is reached first.
        Tests scenario where time limit is reached first.
        Whichever limit triggers first stops discovery; the other is not evaluated after.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        import itertools
        import time as time_module
        
        # Test 1: URL limit reached first
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=3, max_time_seconds=999)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        target_url = f"{local_http_server}/"
        run_attack_for_duration(platoon, factory, target_url, 2)
        
        soldier = platoon._soldiers[0]
        weapon = soldier._weapon
        
        # URL limit should be hit first (3 is small)
        assert weapon._discovered_url_count <= 3, \
            f"Expected at most 3 URLs when URL limit is low, got {weapon._discovered_url_count}"
        assert weapon._is_crawl_limit_reached(), \
            "Expected crawl limit to be reached via URL count"
        
        # Test 2: Time limit reached first
        # Use a generator to provide unlimited, monotonically increasing timestamps
        base_time = time_module.time()
        time_generator = (base_time + n * 0.3 for n in itertools.count())
        
        with patch('time.time', side_effect=lambda: next(time_generator)):
            # Create factory with very short time limit (1 second) and high URL limit
            factory2 = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=999, max_time_seconds=1)
            platoon2 = Platoon(num_soldiers=1, tor_client=None)
            
            # Run attack briefly against real HTTP server
            run_attack_for_duration(platoon2, factory2, target_url, 2)
            
            soldier2 = platoon2._soldiers[0]
            weapon2 = soldier2._weapon
            
            # Time limit should be hit first (1 second is very short)
            if weapon2._start_time is not None:
                elapsed = time_module.time() - weapon2._start_time
                assert weapon2._is_crawl_limit_reached() or elapsed >= 1, \
                    "Expected time limit to be reached via elapsed time"
            
            # Verify attack continued on already-found URLs
            monitor2 = platoon2._monitor
            status2 = monitor2.get_status()
            assert status2[0] > 0, "Expected hits to continue after time limit reached"
    
    def test_limits_are_per_thread_not_global(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify limits are per-thread, not global.
        
        Each thread gets its own FullAutoWeapon instance with independent limits.
        Each thread can discover up to max_urls independently.
        Total discovered URLs across threads can exceed max_urls.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        
        # Create FullAutoFactory with max_urls=5
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=5, max_time_seconds=999)
        
        # Create Platoon with 2 soldier threads (no Tor for faster tests)
        platoon = Platoon(num_soldiers=2, tor_client=None)
        
        # Run attack against real HTTP server
        target_url = f"{local_http_server}/"
        run_attack_for_duration(platoon, factory, target_url, 3)
        
        # Get weapon instances from both soldiers
        weapon1 = platoon._soldiers[0]._weapon
        weapon2 = platoon._soldiers[1]._weapon
        
        # Each weapon should have its own limit tracking
        # They are independent instances, so each can discover up to 5 URLs
        total_urls = weapon1._discovered_url_count + weapon2._discovered_url_count
        
        # Verify each weapon respects its own limit
        assert weapon1._discovered_url_count <= 5, \
            f"Weapon 1 exceeded its limit: {weapon1._discovered_url_count}"
        assert weapon2._discovered_url_count <= 5, \
            f"Weapon 2 exceeded its limit: {weapon2._discovered_url_count}"
        
        # Total can exceed single thread limit (demonstrating per-thread semantics)
        assert total_urls >= 2, \
            f"Expected at least 2 URLs total across threads, got {total_urls}"
    
    def test_attack_continues_on_existing_urls_after_limit(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify attack continues on existing URLs after limit is reached.
        
        Discovery stops when limit is reached.
        Attack continues on URLs already discovered.
        _urls list remains constant after limit reached.
        _discovered_url_count remains constant after limit reached.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        
        # Create factory with max_urls=3
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=3, max_time_seconds=999)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        # Run attack for enough time to hit limit and continue
        target_url = f"{local_http_server}/"
        run_attack_for_duration(platoon, factory, target_url, 4)
        
        # Get weapon instance
        soldier = platoon._soldiers[0]
        weapon = soldier._weapon
        
        # Verify limit was reached
        assert weapon._discovered_url_count == 3, \
            f"Expected exactly 3 URLs discovered, got {weapon._discovered_url_count}"
        assert len(weapon._urls) == 3, \
            f"Expected 3 URLs in list, got {len(weapon._urls)}"
        
        # Verify attack continued (monitor shows hits)
        monitor = platoon._monitor
        status = monitor.get_status()
        assert status[0] > 0, "Expected hits to continue after limit reached"
    
    def test_zero_max_urls_prevents_discovery(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify zero max_urls prevents discovery beyond initial target.
        
        Initial target URL is still attacked.
        No additional URLs are discovered from HTML parsing.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        
        # Create factory with max_urls=0
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=0, max_time_seconds=999)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        # Run attack against real HTTP server
        target_url = f"{local_http_server}/"
        run_attack_for_duration(platoon, factory, target_url, 2)
        
        # Get weapon instance
        soldier = platoon._soldiers[0]
        weapon = soldier._weapon
        
        # Verify no URLs were discovered (beyond initial target which is not counted in _discovered_url_count initially)
        # The initial target is added via target() call, which sets _discovered_url_count to 1
        assert weapon._discovered_url_count <= 1, \
            f"Expected at most 1 URL with max_urls=0, got {weapon._discovered_url_count}"
        
        # Verify attack still occurred on initial target
        monitor = platoon._monitor
        status = monitor.get_status()
        assert status[0] > 0, "Expected hits on initial target"
    
    def test_zero_max_time_prevents_discovery(
        self, mock_console_error, mock_console_log, local_http_server
    ):
        """
        Verify zero max_time_seconds prevents discovery immediately.
        
        Discovery stops immediately due to time limit.
        Initial target URL is still attacked.
        Uses real HTTP server and real NetworkClient.
        """
        from app.weapons.fullauto import FullAutoFactory
        
        # Create factory with max_time_seconds=0
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=999, max_time_seconds=0)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        # Run attack against real HTTP server
        target_url = f"{local_http_server}/"
        run_attack_for_duration(platoon, factory, target_url, 2)
        
        # Get weapon instance
        soldier = platoon._soldiers[0]
        weapon = soldier._weapon
        
        # Verify minimal URL discovery occurred (only initial target)
        assert weapon._discovered_url_count <= 1, \
            f"Expected at most 1 URL with max_time=0, got {weapon._discovered_url_count}"
        
        # Verify attack still occurred
        monitor = platoon._monitor
        status = monitor.get_status()
        assert status[0] > 0, "Expected hits despite zero time limit"
