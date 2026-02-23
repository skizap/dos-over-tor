"""Comprehensive unit tests for the TorClient class.

This module provides complete test coverage for the TorClient class including:
- Connection management (connect, close)
- Identity rotation (new_identity)
- IP lookup (get_current_ip)
- SOCKS5 proxy scoping (proxy_scope)
- Context manager protocol (__enter__, __exit__)
- Error handling and edge cases

All external dependencies (stem, socks, urllib) are mocked to ensure
isolated unit tests that don't require actual Tor or network connections.
"""

import socket
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import socks
import stem
import stem.control

from app.tor import TorClient, ConnectionErrorException


class TestTorClient:
    """Test class for TorClient covering all public methods and edge cases."""

    @pytest.fixture
    def mock_controller(self):
        """Create a mock stem controller with authenticate and signal methods."""
        controller = MagicMock()
        controller.authenticate = MagicMock()
        controller.signal = MagicMock()
        controller.close = MagicMock()
        return controller

    @pytest.fixture
    def mock_stem_module(self, mock_controller):
        """Patch stem.control.Controller.from_port to return mock controller."""
        with patch('app.tor.stem.control.Controller.from_port', return_value=mock_controller) as mock_from_port:
            yield mock_from_port

    @pytest.fixture
    def tor_client(self):
        """Create a fresh TorClient instance for each test."""
        return TorClient()

    # =========================================================================
    # Tests for connect() method
    # =========================================================================

    def test_connect_success_default_params(self, tor_client, mock_stem_module, mock_controller):
        """Test successful connection with default parameters."""
        tor_client.connect()

        # Verify controller was created with default parameters
        mock_stem_module.assert_called_once_with(address='127.0.0.1', port=9051)
        mock_controller.authenticate.assert_called_once()
        assert tor_client._is_connected is True

    def test_connect_success_custom_params(self, tor_client, mock_stem_module, mock_controller):
        """Test successful connection with custom parameters."""
        tor_client.connect(address='192.168.1.1', proxy_port=9150, ctrl_port=9151)

        # Verify controller was created with custom parameters
        mock_stem_module.assert_called_once_with(address='192.168.1.1', port=9151)
        mock_controller.authenticate.assert_called_once()
        assert tor_client._is_connected is True
        assert tor_client._address == '192.168.1.1'
        assert tor_client._proxy_port == 9150
        assert tor_client._ctrl_port == 9151

    def test_connect_failure_raises_exception(self, tor_client):
        """Test connection failure raises ConnectionErrorException."""
        with patch('app.tor.stem.control.Controller.from_port', side_effect=Exception("Connection refused")):
            with pytest.raises(ConnectionErrorException) as exc_info:
                tor_client.connect()

            assert "failed to connect to control port" in str(exc_info.value)
            assert "Connection refused" in str(exc_info.value)

    def test_connect_sets_connected_flag(self, tor_client, mock_stem_module, mock_controller):
        """Test that connection sets _is_connected flag to True."""
        assert tor_client._is_connected is False

        tor_client.connect()

        assert tor_client._is_connected is True

    def test_connect_stores_parameters(self, tor_client, mock_stem_module, mock_controller):
        """Test that connection stores address, proxy_port, and ctrl_port."""
        tor_client.connect(address='10.0.0.1', proxy_port=8080, ctrl_port=8081)

        assert tor_client._address == '10.0.0.1'
        assert tor_client._proxy_port == 8080
        assert tor_client._ctrl_port == 8081

    # =========================================================================
    # Tests for new_identity() method
    # =========================================================================

    def test_new_identity_success(self, tor_client, mock_stem_module, mock_controller):
        """Test successful identity rotation sends NEWNYM signal."""
        tor_client.connect()
        tor_client.new_identity()

        # Verify NEWNYM signal was sent
        mock_controller.signal.assert_called_once_with(stem.Signal.NEWNYM)

    def test_new_identity_without_connection_raises(self, tor_client):
        """Test calling new_identity without connection raises ConnectionErrorException."""
        with pytest.raises(ConnectionErrorException) as exc_info:
            tor_client.new_identity()

        assert "cannot request new identity; not connected to Tor controller" in str(exc_info.value)

    def test_new_identity_passes_newnym_signal(self, tor_client, mock_stem_module, mock_controller):
        """Test that stem.Signal.NEWNYM is passed to controller."""
        tor_client.connect()
        tor_client.new_identity()

        # Verify the correct signal constant was passed
        call_args = mock_controller.signal.call_args[0]
        assert call_args[0] == stem.Signal.NEWNYM

    # =========================================================================
    # Tests for get_current_ip() method
    # =========================================================================

    def test_get_current_ip_success(self, tor_client):
        """Test successful IP lookup returns IP string."""
        # Mock the URL open to return a fake IP
        mock_response = MagicMock()
        mock_response.read.return_value = b'192.168.1.100\n'

        with patch('app.tor.urllib.request.urlopen', return_value=mock_response):
            ip = tor_client.get_current_ip()

        assert ip == '192.168.1.100'

    def test_get_current_ip_failure_raises_exception(self, tor_client):
        """Test IP lookup failure raises ConnectionErrorException."""
        with patch('app.tor.urllib.request.urlopen', side_effect=Exception("Network timeout")):
            with pytest.raises(ConnectionErrorException) as exc_info:
                tor_client.get_current_ip()

            assert "failed to get current IP" in str(exc_info.value)
            assert "Network timeout" in str(exc_info.value)

    def test_get_current_ip_decodes_and_strips(self, tor_client):
        """Test that response is properly decoded and stripped."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'  10.0.0.1  \r\n'

        with patch('app.tor.urllib.request.urlopen', return_value=mock_response):
            ip = tor_client.get_current_ip()

        assert ip == '10.0.0.1'

    # =========================================================================
    # Tests for proxy_scope() context manager
    # =========================================================================

    def test_proxy_scope_configures_socks(self, tor_client, mock_stem_module, mock_controller):
        """Test proxy setup configures socks with correct parameters."""
        tor_client.connect(address='192.168.1.1', proxy_port=9150)

        with patch('app.tor.socks.setdefaultproxy') as mock_setdefaultproxy:
            with patch('app.tor.socket.socket') as mock_socket_class:
                with tor_client.proxy_scope():
                    pass

                # Verify socks configuration
                mock_setdefaultproxy.assert_called_once_with(
                    socks.PROXY_TYPE_SOCKS5,
                    '192.168.1.1',
                    9150,
                    True  # rdns=True
                )

    def test_proxy_scope_replaces_socket(self, tor_client, mock_stem_module, mock_controller):
        """Test that socket.socket is replaced with socks.socksocket during scope."""
        tor_client.connect()

        original_socket = socket.socket

        with patch('app.tor.socks.setdefaultproxy'):
            with tor_client.proxy_scope():
                # During scope, socket.socket should be socksocket
                assert socket.socket == socks.socksocket

        # After scope, original socket should be restored
        assert socket.socket == original_socket

    def test_proxy_scope_restores_socket_on_exit(self, tor_client, mock_stem_module, mock_controller):
        """Test proxy teardown restores original socket."""
        tor_client.connect()

        original_socket = socket.socket

        with patch('app.tor.socks.setdefaultproxy'):
            with tor_client.proxy_scope():
                pass

        # Verify original socket is restored
        assert socket.socket == original_socket

    def test_proxy_scope_restores_socket_on_exception(self, tor_client, mock_stem_module, mock_controller):
        """Test that original socket is restored even on exception."""
        tor_client.connect()

        original_socket = socket.socket

        with patch('app.tor.socks.setdefaultproxy'):
            try:
                with tor_client.proxy_scope():
                    raise ValueError("Test exception")
            except ValueError:
                pass

        # Verify original socket is restored even after exception
        assert socket.socket == original_socket

    def test_proxy_scope_setdefaultproxy_called_with_socks5(self, tor_client, mock_stem_module, mock_controller):
        """Test that socks.setdefaultproxy is called with PROXY_TYPE_SOCKS5."""
        tor_client.connect()

        with patch('app.tor.socks.setdefaultproxy') as mock_setdefaultproxy:
            with tor_client.proxy_scope():
                pass

            # Verify PROXY_TYPE_SOCKS5 was used
            call_args = mock_setdefaultproxy.call_args[0]
            assert call_args[0] == socks.PROXY_TYPE_SOCKS5

    def test_proxy_scope_called_with_rdns_true(self, tor_client, mock_stem_module, mock_controller):
        """Test that socks.setdefaultproxy is called with rdns=True."""
        tor_client.connect()

        with patch('app.tor.socks.setdefaultproxy') as mock_setdefaultproxy:
            with tor_client.proxy_scope():
                pass

            # Verify rdns=True (4th parameter)
            call_args = mock_setdefaultproxy.call_args[0]
            assert call_args[3] is True

    def test_proxy_scope_failure_raises_connection_error(self, tor_client, mock_stem_module, mock_controller):
        """Test proxy setup failure raises ConnectionErrorException."""
        tor_client.connect()

        with patch('app.tor.socks.setdefaultproxy', side_effect=Exception("SOCKS error")):
            with pytest.raises(ConnectionErrorException) as exc_info:
                with tor_client.proxy_scope():
                    pass

            assert "failed to set up proxy" in str(exc_info.value)
            assert "SOCKS error" in str(exc_info.value)

    # =========================================================================
    # Tests for close() method
    # =========================================================================

    def test_close_calls_controller_close(self, tor_client, mock_stem_module, mock_controller):
        """Test close() calls controller.close()."""
        tor_client.connect()
        tor_client.close()

        mock_controller.close.assert_called_once()

    def test_close_sets_is_connected_false(self, tor_client, mock_stem_module, mock_controller):
        """Test close() sets _is_connected to False."""
        tor_client.connect()
        assert tor_client._is_connected is True

        tor_client.close()

        assert tor_client._is_connected is False

    def test_close_can_be_called_multiple_times_safely(self, tor_client, mock_stem_module, mock_controller):
        """Test close() can be called multiple times safely."""
        tor_client.connect()
        tor_client.close()

        # Should not raise an exception
        tor_client.close()
        tor_client.close()

    def test_close_sets_controller_none(self, tor_client, mock_stem_module, mock_controller):
        """Test close() sets _controller to None."""
        tor_client.connect()
        assert tor_client._controller is not None

        tor_client.close()

        assert tor_client._controller is None

    def test_close_safely_when_not_connected(self, tor_client):
        """Test close() can be called safely when not connected."""
        # Should not raise an exception
        tor_client.close()

    # =========================================================================
    # Tests for context manager protocol
    # =========================================================================

    def test_enter_returns_client_instance(self, tor_client):
        """Test __enter__ returns the client instance."""
        result = tor_client.__enter__()

        assert result is tor_client

    def test_exit_calls_close(self, tor_client, mock_stem_module, mock_controller):
        """Test __exit__ calls close() automatically."""
        tor_client.connect()

        with tor_client:
            pass

        mock_controller.close.assert_called_once()

    def test_exit_calls_close_on_exception(self, tor_client, mock_stem_module, mock_controller):
        """Test __exit__ calls close() even when exception occurs."""
        tor_client.connect()

        try:
            with tor_client:
                raise ValueError("Test exception")
        except ValueError:
            pass

        mock_controller.close.assert_called_once()

    def test_context_manager_usage(self, tor_client, mock_stem_module, mock_controller):
        """Test full context manager usage pattern."""
        with tor_client as client:
            client.connect()
            assert client._is_connected is True

        # After exiting context, should be closed
        assert tor_client._is_connected is False
        mock_controller.close.assert_called_once()


class TestTorClientSingletonFunctions:
    """Tests for module-level singleton wrapper functions."""

    def test_connect_creates_singleton(self):
        """Test that connect() creates module-level singleton."""
        import app.tor as tor_module

        # Reset the singleton
        tor_module._tor_client = None

        with patch('app.tor.stem.control.Controller.from_port') as mock_from_port:
            mock_controller = MagicMock()
            mock_controller.authenticate = MagicMock()
            mock_controller.close = MagicMock()
            mock_from_port.return_value = mock_controller

            tor_module.connect()

            assert tor_module._tor_client is not None
            assert isinstance(tor_module._tor_client, TorClient)

        # Cleanup
        tor_module._tor_client = None

    def test_connect_uses_existing_singleton(self):
        """Test that connect() reuses existing singleton."""
        import app.tor as tor_module

        # Reset the singleton
        tor_module._tor_client = None

        with patch('app.tor.stem.control.Controller.from_port') as mock_from_port:
            mock_controller = MagicMock()
            mock_controller.authenticate = MagicMock()
            mock_controller.close = MagicMock()
            mock_from_port.return_value = mock_controller

            tor_module.connect()
            first_client = tor_module._tor_client

            # Call connect again
            tor_module.connect()
            second_client = tor_module._tor_client

            assert first_client is second_client

        # Cleanup
        tor_module._tor_client = None

    def test_new_ident_without_connect_raises(self):
        """Test that new_ident() raises if connect() not called."""
        import app.tor as tor_module

        # Reset the singleton
        tor_module._tor_client = None

        with pytest.raises(ConnectionErrorException) as exc_info:
            tor_module.new_ident()

        assert "not connected; call connect() first" in str(exc_info.value)

    def test_close_singleton(self):
        """Test that close() properly closes and clears singleton."""
        import app.tor as tor_module

        with patch('app.tor.stem.control.Controller.from_port') as mock_from_port:
            mock_controller = MagicMock()
            mock_controller.authenticate = MagicMock()
            mock_controller.close = MagicMock()
            mock_from_port.return_value = mock_controller

            tor_module.connect()
            assert tor_module._tor_client is not None

            tor_module.close()

            assert tor_module._tor_client is None


class TestTorClientInitialization:
    """Tests for TorClient initialization and default values."""

    def test_default_values(self):
        """Test that TorClient initializes with correct default values."""
        client = TorClient()

        assert client._controller is None
        assert client._address == '127.0.0.1'
        assert client._proxy_port == 9050
        assert client._ctrl_port == 9051
        assert client._is_connected is False
