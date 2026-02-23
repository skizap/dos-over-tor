"""Comprehensive unit tests for the SlowLorisWeapon class.

This module provides complete test coverage for the SlowLorisWeapon class including:
- Initialization with correct defaults and parameters (num_sockets)
- Socket spawning with correct HTTP headers and byte tracking
- Keep-alive header sending to maintain connections
- Successful attack execution with proper AttackResult population
- Error handling for socket errors
- Byte tracking for all sent data
- Socket management (growth, failure handling, cleanup)
- Monitor integration for active socket counting
- Hold fire functionality for cleanup
- HTTP vs HTTPS connection handling
- SSL wrapping for secure connections

All external dependencies (socket, ssl, NetworkClient, time, random) are mocked
to ensure isolated unit tests that don't require actual network connections.
"""

import pytest
import socket
import ssl
import time
import random
from unittest.mock import MagicMock, patch, Mock, call
from urllib.parse import urlparse
from app.models import AttackResult
from app.weapons.slowloris import SlowLorisWeapon
from app.net import NetworkClient


class TestSlowLorisWeaponInitialization:
    """Test cases for SlowLorisWeapon initialization."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_weapon_initializes_with_default_num_sockets(self, weapon):
        """Test weapon initializes with correct num_sockets (default 100)."""
        assert weapon._num_sockets == 100

    def test_weapon_initializes_with_custom_num_sockets(self):
        """Test weapon initializes with custom num_sockets."""
        weapon = SlowLorisWeapon(num_sockets=50)
        assert weapon._num_sockets == 50

    def test_weapon_initializes_with_empty_sockets_list(self, weapon):
        """Test weapon initializes with empty _sockets list."""
        assert weapon._sockets == []

    @patch('app.weapons.slowloris.NetworkClient')
    def test_network_client_instance_is_created(self, mock_network_client_class):
        """Test NetworkClient instance is created during initialization."""
        SlowLorisWeapon()
        mock_network_client_class.assert_called_once()

    @patch('app.weapons.slowloris.NetworkClient')
    def test_rotate_user_agent_is_called_during_initialization(self, mock_network_client_class):
        """Test rotate_user_agent() is called during initialization."""
        mock_client = MagicMock()
        mock_network_client_class.return_value = mock_client

        SlowLorisWeapon()

        mock_client.rotate_user_agent.assert_called_once()


class TestSlowLorisWeaponSocketSpawning:
    """Test cases for SlowLorisWeapon _spawn_socket() method."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_spawn_socket_creates_socket_with_correct_parameters(self, weapon):
        """Test _spawn_socket() creates socket with correct parameters."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'

        mock_socket = MagicMock()

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket) as mock_socket_class:
            with patch.object(mock_socket, 'connect'):
                with patch.object(mock_socket, 'send'):
                    with patch('app.weapons.slowloris.ssl.create_default_context'):
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            weapon._spawn_socket('https://example.com')

        # Verify socket was created with correct parameters
        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_socket.settimeout.assert_called_once_with(4)

    def test_spawn_socket_returns_tuple_of_socket_and_bytes_sent(self, weapon):
        """Test _spawn_socket() returns tuple of (socket, bytes_sent)."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch.object(mock_socket, 'send'):
                    with patch('app.weapons.slowloris.ssl.create_default_context'):
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            result = weapon._spawn_socket('https://example.com')

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], int)  # bytes_sent

    def test_spawn_socket_sends_http_request_line(self, weapon):
        """Test _spawn_socket() sends HTTP request line."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestAgent'
                        weapon._spawn_socket('https://example.com')

        # Check that HTTP request line was sent
        http_line = b'GET / HTTP/1.1\r\n'
        assert any(http_line in data for data in sent_data)

    def test_spawn_socket_sends_host_header(self, weapon):
        """Test _spawn_socket() sends Host header."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestAgent'
                        weapon._spawn_socket('https://example.com')

        # Check that Host header was sent
        host_header = b'Host: example.com\r\n'
        assert any(data == host_header for data in sent_data)

    def test_spawn_socket_sends_user_agent_header(self, weapon):
        """Test _spawn_socket() sends User-Agent header."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestUserAgent'
                        weapon._spawn_socket('https://example.com')

        # Check that User-Agent header was sent
        user_agent_header = b'User-Agent: TestUserAgent\r\n'
        assert any(data == user_agent_header for data in sent_data)

    def test_spawn_socket_sends_accept_language_header(self, weapon):
        """Test _spawn_socket() sends Accept-language header."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestAgent'
                        weapon._spawn_socket('https://example.com')

        # Check that Accept-language header was sent
        accept_lang_header = b'Accept-language: en-US,en,q=0.5\r\n'
        assert any(data == accept_lang_header for data in sent_data)

    def test_spawn_socket_tracks_bytes_sent_for_all_headers(self, weapon):
        """Test _spawn_socket() tracks bytes sent for all headers."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestAgent'
                        sock, bytes_sent = weapon._spawn_socket('https://example.com')

        # Should have bytes for: HTTP line + Host + User-Agent + Accept-language
        assert bytes_sent > 0
        # HTTP line: "GET / HTTP/1.1\r\n" = 16 bytes
        # Host: "Host: example.com\r\n" = 22 bytes
        # User-Agent: "User-Agent: TestAgent\r\n" = 25 bytes
        # Accept-language: "Accept-language: en-US,en,q=0.5\r\n" = 37 bytes
        assert bytes_sent >= 100  # Should be at least this much

    def test_https_connections_use_ssl_wrapping(self, weapon):
        """Test HTTPS connections use SSL wrapping."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'

        mock_socket = MagicMock()
        mock_context = MagicMock()
        mock_wrapped_socket = MagicMock()
        mock_context.wrap_socket.return_value = mock_wrapped_socket

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch('app.weapons.slowloris.ssl.create_default_context', return_value=mock_context) as mock_create_context:
                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                    with patch.object(mock_wrapped_socket, 'connect'):
                        with patch.object(mock_wrapped_socket, 'send'):
                            weapon._network_client = MagicMock()
                            weapon._network_client.get_user_agent.return_value = 'TestAgent'
                            weapon._spawn_socket('https://example.com')

        mock_create_context.assert_called_once()
        mock_context.wrap_socket.assert_called_once_with(mock_socket, server_hostname='example.com')

    def test_http_connections_use_plain_sockets(self, weapon):
        """Test HTTP connections use plain sockets (no SSL)."""
        weapon._target_url = 'http://example.com'
        weapon._http_method = 'GET'

        mock_socket = MagicMock()

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket) as mock_socket_class:
            with patch.object(mock_socket, 'connect'):
                with patch.object(mock_socket, 'send'):
                    with patch('app.weapons.slowloris.ssl.create_default_context') as mock_create_context:
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            weapon._network_client = MagicMock()
                            weapon._network_client.get_user_agent.return_value = 'TestAgent'
                            weapon._spawn_socket('http://example.com')

        mock_create_context.assert_not_called()

    def test_cache_buster_adds_random_query_parameter(self, weapon):
        """Test cache buster adds random query parameter to HTTP line."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = True

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.random.randint', return_value=1234):
            with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
                with patch.object(mock_socket, 'connect'):
                    with patch('app.weapons.slowloris.ssl.create_default_context'):
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            weapon._network_client = MagicMock()
                            weapon._network_client.get_user_agent.return_value = 'TestAgent'
                            weapon._spawn_socket('https://example.com')

        # Check that HTTP line includes random query parameter
        http_line_with_cache_buster = b'GET /?1234 HTTP/1.1\r\n'
        assert any(data == http_line_with_cache_buster for data in sent_data)


class TestSlowLorisWeaponSuccessPath:
    """Test cases for SlowLorisWeapon successful attack execution."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon(num_sockets=3)

    def test_attack_returns_attackresult_with_correct_num_hits(self, weapon):
        """Test attack() returns AttackResult with correct num_hits."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 3

        # Pre-populate with 3 sockets
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        mock_sock3 = MagicMock()
        weapon._sockets = [mock_sock1, mock_sock2, mock_sock3]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.num_hits == 3  # One hit per socket

    def test_num_hits_equals_number_of_keepalive_headers_sent(self, weapon):
        """Test num_hits equals number of keep-alive headers sent."""
        weapon._target_url = 'https://example.com'

        # Pre-populate with 2 sockets
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        weapon._sockets = [mock_sock1, mock_sock2]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', side_effect=[100, 200]):
                result = weapon.attack()

        # Each socket should have received a keep-alive header
        assert mock_sock1.send.called
        assert mock_sock2.send.called
        assert result.num_hits == 2

    def test_http_status_200_when_sockets_healthy(self, weapon):
        """Test http_status=200 when sockets are healthy (>= num_sockets)."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 3

        # Pre-populate with exactly 3 sockets (healthy state)
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        mock_sock3 = MagicMock()
        weapon._sockets = [mock_sock1, mock_sock2, mock_sock3]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.http_status == 200

    def test_http_status_429_when_sockets_dying(self, weapon):
        """Test http_status=429 when sockets are dying (< num_sockets)."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 5

        # Pre-populate with only 2 sockets (dying state)
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        weapon._sockets = [mock_sock1, mock_sock2]

        # Mock additional socket to avoid real network calls
        mock_new_sock = MagicMock()

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', return_value=mock_new_sock):
                    with patch.object(mock_new_sock, 'connect'):
                        with patch.object(mock_new_sock, 'send'):
                            with patch('app.weapons.slowloris.ssl.create_default_context'):
                                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                                    weapon._network_client = MagicMock()
                                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                                    result = weapon.attack()

        assert result.http_status == 429

    def test_bytes_sent_accumulates_from_keepalive_headers(self, weapon):
        """Test bytes_sent accumulates from keep-alive headers."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.bytes_sent > 0  # Should have bytes from keep-alive header

    def test_bytes_sent_accumulates_from_socket_spawning(self, weapon):
        """Test bytes_sent accumulates from socket spawning."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 1
        weapon._sockets = []  # Empty, will spawn new socket

        mock_sock = MagicMock()

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', return_value=mock_sock):
                    with patch.object(mock_sock, 'connect'):
                        with patch.object(mock_sock, 'send'):
                            with patch('app.weapons.slowloris.ssl.create_default_context'):
                                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                                    weapon._network_client = MagicMock()
                                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                                    result = weapon.attack()

        assert result.bytes_sent > 0

    def test_bytes_received_is_0(self, weapon):
        """Test bytes_received=0 (slowloris doesn't receive data)."""
        weapon._target_url = 'https://example.com'
        weapon._sockets = [MagicMock()]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.bytes_received == 0

    def test_response_time_ms_is_none(self, weapon):
        """Test response_time_ms=None (slowloris doesn't track response time)."""
        weapon._target_url = 'https://example.com'
        weapon._sockets = [MagicMock()]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.response_time_ms is None

    def test_errors_0_when_no_socket_errors(self, weapon):
        """Test errors=0 when no socket errors occur."""
        weapon._target_url = 'https://example.com'
        weapon._sockets = [MagicMock()]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.errors == 0


class TestSlowLorisWeaponKeepAlive:
    """Test cases for SlowLorisWeapon keep-alive header functionality."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_keepalive_headers_sent_to_existing_sockets(self, weapon):
        """Test keep-alive headers are sent to existing sockets."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                weapon.attack()

        assert mock_sock.send.called

    def test_keepalive_header_format(self, weapon):
        """Test keep-alive header format: 'X-a: <random>\r\n'."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_sock.send.side_effect = capture_send
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=1234):
                weapon.attack()

        # Check that keep-alive header was sent with correct format
        keep_alive_header = b'X-a: 1234\r\n'
        assert any(data == keep_alive_header for data in sent_data)

    def test_bytes_tracked_for_each_keepalive_header(self, weapon):
        """Test bytes are tracked for each keep-alive header."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        # Should have bytes for keep-alive header
        assert result.bytes_sent >= len(b'X-a: 100\r\n')

    def test_time_sleep_13_called_after_sending_headers(self, weapon):
        """Test time.sleep(13) is called after sending keep-alive headers."""
        weapon._target_url = 'https://example.com'
        weapon._sockets = [MagicMock()]

        with patch('app.weapons.slowloris.time.sleep') as mock_sleep:
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                weapon.attack()

        mock_sleep.assert_called_once_with(13)


class TestSlowLorisWeaponSocketManagement:
    """Test cases for SlowLorisWeapon socket management."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon(num_sockets=3)

    def test_sockets_spawned_up_to_num_sockets_limit(self, weapon):
        """Test sockets are spawned up to num_sockets limit."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 3
        weapon._sockets = []  # Start with 0 sockets

        mock_sock = MagicMock()
        spawn_count = [0]

        def track_socket_creation(*args, **kwargs):
            spawn_count[0] += 1
            return mock_sock

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', side_effect=track_socket_creation):
                    with patch.object(mock_sock, 'connect'):
                        with patch.object(mock_sock, 'send'):
                            with patch('app.weapons.slowloris.ssl.create_default_context'):
                                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                                    weapon._network_client = MagicMock()
                                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                                    weapon.attack()

        # Should have created 3 sockets (to reach num_sockets limit)
        assert spawn_count[0] == 3
        assert len(weapon._sockets) == 3

    def test_failed_sockets_removed_from_list(self, weapon):
        """Test failed sockets are removed from list."""
        weapon._target_url = 'https://example.com'

        # Create a socket that will fail on keep-alive
        mock_sock = MagicMock()
        mock_sock.send.side_effect = socket.error("Connection reset")
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                weapon.attack()

        # Failed socket should be removed
        assert mock_sock not in weapon._sockets
        assert len(weapon._sockets) == 0

    def test_socket_list_grows_from_0_to_num_sockets(self, weapon):
        """Test socket list grows from 0 to num_sockets."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 2
        weapon._sockets = []

        mock_sock = MagicMock()

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', return_value=mock_sock):
                    with patch.object(mock_sock, 'connect'):
                        with patch.object(mock_sock, 'send'):
                            with patch('app.weapons.slowloris.ssl.create_default_context'):
                                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                                    weapon._network_client = MagicMock()
                                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                                    weapon.attack()

        assert len(weapon._sockets) == weapon._num_sockets


class TestSlowLorisWeaponErrorHandling:
    """Test cases for SlowLorisWeapon error handling."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_socket_error_during_keepalive_increments_error_count(self, weapon):
        """Test socket.error during keep-alive increments error count."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        mock_sock.send.side_effect = socket.error("Connection reset")
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.errors == 1

    def test_socket_error_during_keepalive_removes_socket_from_list(self, weapon):
        """Test socket.error during keep-alive removes socket from list."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        mock_sock.send.side_effect = socket.error("Connection reset")
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                weapon.attack()

        assert mock_sock not in weapon._sockets

    def test_socket_error_during_spawning_increments_error_count(self, weapon):
        """Test socket.error during spawning increments error count."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 1
        weapon._sockets = []

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', side_effect=socket.error("Cannot create socket")):
                    result = weapon.attack()

        assert result.errors == 1

    def test_socket_error_during_spawning_breaks_spawn_loop(self, weapon):
        """Test socket.error during spawning breaks spawn loop."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 5
        weapon._sockets = []

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', side_effect=socket.error("Cannot create socket")):
                    result = weapon.attack()

        # Should have 0 sockets since spawn failed
        assert len(weapon._sockets) == 0

    def test_errors_accumulated_in_attackresult_errors(self, weapon):
        """Test errors are accumulated in AttackResult.errors."""
        weapon._target_url = 'https://example.com'

        # Create 2 sockets that will fail on keep-alive
        mock_sock1 = MagicMock()
        mock_sock1.send.side_effect = socket.error("Connection reset")
        mock_sock2 = MagicMock()
        mock_sock2.send.side_effect = socket.error("Connection reset")
        weapon._sockets = [mock_sock1, mock_sock2]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert result.errors == 2


class TestSlowLorisWeaponHoldFire:
    """Test cases for SlowLorisWeapon hold_fire() method."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_hold_fire_closes_all_open_sockets(self, weapon):
        """Test hold_fire() closes all open sockets."""
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        weapon._sockets = [mock_sock1, mock_sock2]

        weapon.hold_fire()

        mock_sock1.close.assert_called_once()
        mock_sock2.close.assert_called_once()

    def test_hold_fire_clears_sockets_list(self, weapon):
        """Test hold_fire() clears _sockets list."""
        mock_sock = MagicMock()
        weapon._sockets = [mock_sock]

        weapon.hold_fire()

        assert weapon._sockets == []

    def test_hold_fire_handles_socket_close_errors_gracefully(self, weapon):
        """Test hold_fire() handles socket close errors gracefully."""
        mock_sock = MagicMock()
        mock_sock.close.side_effect = socket.error("Already closed")
        weapon._sockets = [mock_sock]

        # Should not raise
        weapon.hold_fire()

        # Socket list should still be cleared
        assert weapon._sockets == []


class TestSlowLorisWeaponByteTracking:
    """Test cases for SlowLorisWeapon byte tracking."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_bytes_from_http_request_line(self, weapon):
        """Test bytes from HTTP request line."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = False

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestAgent'
                        sock, bytes_sent = weapon._spawn_socket('https://example.com')

        # Should include bytes for HTTP request line
        assert bytes_sent >= len(b'GET / HTTP/1.1\r\n')

    def test_bytes_from_all_headers(self, weapon):
        """Test bytes from all headers (Host, User-Agent, Accept-language)."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'connect'):
                with patch('app.weapons.slowloris.ssl.create_default_context'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'Mozilla/5.0'
                        sock, bytes_sent = weapon._spawn_socket('https://example.com')

        # Calculate expected bytes
        expected_http_line = len(b'GET / HTTP/1.1\r\n')
        expected_host = len(b'Host: example.com\r\n')
        expected_user_agent = len(b'User-Agent: Mozilla/5.0\r\n')
        expected_accept_lang = len(b'Accept-language: en-US,en,q=0.5\r\n')
        expected_total = expected_http_line + expected_host + expected_user_agent + expected_accept_lang

        assert bytes_sent == expected_total

    def test_bytes_from_keepalive_headers(self, weapon):
        """Test bytes from keep-alive headers."""
        weapon._target_url = 'https://example.com'

        mock_sock = MagicMock()
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=1234):
                result = weapon.attack()

        # Should have bytes for keep-alive header: "X-a: 1234\r\n"
        expected_keepalive = len(b'X-a: 1234\r\n')
        assert result.bytes_sent >= expected_keepalive

    def test_total_bytes_accumulate_correctly(self, weapon):
        """Test total bytes accumulate correctly."""
        weapon._target_url = 'https://example.com'

        # One existing socket that will receive keep-alive
        mock_existing_sock = MagicMock()
        weapon._sockets = [mock_existing_sock]

        # Mock a new socket that will be spawned
        mock_new_sock = MagicMock()
        spawn_count = [0]

        def track_socket_creation(*args, **kwargs):
            spawn_count[0] += 1
            return mock_new_sock

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', side_effect=track_socket_creation):
                    with patch.object(mock_new_sock, 'connect'):
                        with patch.object(mock_new_sock, 'send'):
                            with patch('app.weapons.slowloris.ssl.create_default_context'):
                                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                                    weapon._network_client = MagicMock()
                                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                                    result = weapon.attack()

        # Should have bytes from keep-alive + from spawning
        assert result.bytes_sent > 0

    def test_bytes_with_cache_buster_enabled(self, weapon):
        """Test bytes with cache buster enabled."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'
        weapon._cache_buster = True

        mock_socket = MagicMock()
        sent_data = []

        def capture_send(data):
            sent_data.append(data)
            return len(data)

        mock_socket.send.side_effect = capture_send

        with patch('app.weapons.slowloris.random.randint', return_value=1234):
            with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
                with patch.object(mock_socket, 'connect'):
                    with patch('app.weapons.slowloris.ssl.create_default_context'):
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            weapon._network_client = MagicMock()
                            weapon._network_client.get_user_agent.return_value = 'TestAgent'
                            sock, bytes_sent = weapon._spawn_socket('https://example.com')

        # HTTP line with cache buster should be longer
        assert bytes_sent > len(b'GET / HTTP/1.1\r\n')


class TestSlowLorisWeaponMonitorIntegration:
    """Test cases for SlowLorisWeapon monitor integration."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_increment_active_sockets_called_when_monitor_set(self, weapon):
        """Test increment_active_sockets() called when monitor is set."""
        weapon._target_url = 'https://example.com'
        weapon._num_sockets = 1
        weapon._sockets = []

        mock_monitor = MagicMock()
        weapon._monitor = mock_monitor

        mock_sock = MagicMock()

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                with patch('app.weapons.slowloris.socket.socket', return_value=mock_sock):
                    with patch.object(mock_sock, 'connect'):
                        with patch.object(mock_sock, 'send'):
                            with patch('app.weapons.slowloris.ssl.create_default_context'):
                                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                                    weapon._network_client = MagicMock()
                                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                                    weapon.attack()

        mock_monitor.increment_active_sockets.assert_called_once()

    def test_decrement_active_sockets_called_when_socket_fails(self, weapon):
        """Test decrement_active_sockets() called when socket fails."""
        weapon._target_url = 'https://example.com'

        mock_monitor = MagicMock()
        weapon._monitor = mock_monitor

        mock_sock = MagicMock()
        mock_sock.send.side_effect = socket.error("Connection reset")
        weapon._sockets = [mock_sock]

        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                weapon.attack()

        mock_monitor.decrement_active_sockets.assert_called_once()

    def test_no_errors_when_monitor_is_none(self, weapon):
        """Test no errors when monitor is None."""
        weapon._target_url = 'https://example.com'
        weapon._monitor = None
        weapon._sockets = [MagicMock()]

        # Should not raise
        with patch('app.weapons.slowloris.time.sleep'):
            with patch('app.weapons.slowloris.random.randint', return_value=100):
                result = weapon.attack()

        assert isinstance(result, AttackResult)

    def test_hold_fire_calls_decrement_active_sockets_with_count(self, weapon):
        """Test hold_fire() calls decrement_active_sockets() with count."""
        weapon._monitor = MagicMock()

        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        weapon._sockets = [mock_sock1, mock_sock2]

        weapon.hold_fire()

        weapon._monitor.decrement_active_sockets.assert_called_once_with(2)


class TestSlowLorisWeaponHttpVsHttps:
    """Test cases for SlowLorisWeapon HTTP vs HTTPS handling."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SlowLorisWeapon instance for each test."""
        return SlowLorisWeapon()

    def test_http_uses_port_80(self, weapon):
        """Test HTTP uses port 80."""
        weapon._target_url = 'http://example.com'
        weapon._http_method = 'GET'

        mock_socket = MagicMock()
        connect_calls = []

        def capture_connect(addr):
            connect_calls.append(addr)

        mock_socket.connect.side_effect = capture_connect

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch.object(mock_socket, 'send'):
                with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                    weapon._network_client = MagicMock()
                    weapon._network_client.get_user_agent.return_value = 'TestAgent'
                    weapon._spawn_socket('http://example.com')

        assert connect_calls[0][1] == 80  # Port 80 for HTTP

    def test_https_uses_port_443(self, weapon):
        """Test HTTPS uses port 443."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'

        mock_socket = MagicMock()
        mock_wrapped = MagicMock()
        connect_calls = []

        def capture_connect(addr):
            connect_calls.append(addr)

        mock_wrapped.connect.side_effect = capture_connect

        mock_context = MagicMock()
        mock_context.wrap_socket.return_value = mock_wrapped

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch('app.weapons.slowloris.ssl.create_default_context', return_value=mock_context):
                with patch.object(mock_wrapped, 'send'):
                    with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                        weapon._network_client = MagicMock()
                        weapon._network_client.get_user_agent.return_value = 'TestAgent'
                        weapon._spawn_socket('https://example.com')

        assert connect_calls[0][1] == 443  # Port 443 for HTTPS

    def test_https_wraps_socket_with_ssl(self, weapon):
        """Test HTTPS wraps socket with SSL."""
        weapon._target_url = 'https://example.com'

        mock_socket = MagicMock()
        mock_wrapped = MagicMock()

        mock_context = MagicMock()
        mock_context.wrap_socket.return_value = mock_wrapped

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch('app.weapons.slowloris.ssl.create_default_context', return_value=mock_context) as mock_create_context:
                with patch.object(mock_wrapped, 'connect'):
                    with patch.object(mock_wrapped, 'send'):
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            weapon._network_client = MagicMock()
                            weapon._network_client.get_user_agent.return_value = 'TestAgent'
                            weapon._spawn_socket('https://example.com')

        mock_context.wrap_socket.assert_called_once_with(mock_socket, server_hostname='example.com')

    def test_ssl_context_settings(self, weapon):
        """Test SSL context settings (check_hostname=False, verify_mode=CERT_NONE)."""
        weapon._target_url = 'https://example.com'

        mock_socket = MagicMock()
        mock_context = MagicMock()

        with patch('app.weapons.slowloris.socket.socket', return_value=mock_socket):
            with patch('app.weapons.slowloris.ssl.create_default_context', return_value=mock_context) as mock_create_context:
                with patch.object(mock_socket, 'connect'):
                    with patch.object(mock_socket, 'send'):
                        with patch('app.weapons.slowloris.socket.gethostbyname', return_value='192.168.1.1'):
                            weapon._network_client = MagicMock()
                            weapon._network_client.get_user_agent.return_value = 'TestAgent'
                            weapon._spawn_socket('https://example.com')

        assert mock_context.check_hostname is False
        assert mock_context.verify_mode == ssl.CERT_NONE
