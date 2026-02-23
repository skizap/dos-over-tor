"""Unit tests for the PreFlightValidator class.

This module contains comprehensive tests for the PreFlightValidator,
following the established patterns from test_tor_client.py. Tests cover
successful validation scenarios, various failure modes, and configuration
display behavior.

Test Classes:
    TestPreFlightValidator: Main test class containing all validator tests.

Fixtures:
    validator: Creates a PreFlightValidator instance.
    mock_tor_client: Creates a mock TorClient for testing.
    attack_config_singleshot: Creates a singleshot AttackConfig fixture.
    attack_config_fullauto: Creates a fullauto AttackConfig fixture.
    attack_config_slowloris: Creates a slowloris AttackConfig fixture.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.preflight import PreFlightValidator
from app.models import AttackConfig
from app.tor import ConnectionErrorException


class TestPreFlightValidator:
    """Tests for PreFlightValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a PreFlightValidator instance."""
        return PreFlightValidator()

    @pytest.fixture
    def mock_tor_client(self):
        """Create a mock TorClient for testing."""
        mock = MagicMock()
        mock._is_connected = True
        mock.proxy_scope = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=None)
        ))
        mock.get_current_ip = MagicMock(return_value='192.168.1.100')
        return mock

    @pytest.fixture
    def attack_config_singleshot(self):
        """Create a singleshot mode AttackConfig."""
        return AttackConfig(
            mode='singleshot',
            target='https://example.com',
            num_threads=10,
            http_method='GET',
            cache_buster=False,
            identity_rotation_interval=None
        )

    @pytest.fixture
    def attack_config_fullauto(self):
        """Create a fullauto mode AttackConfig."""
        return AttackConfig(
            mode='fullauto',
            target='https://example.com',
            num_threads=20,
            http_method='POST',
            cache_buster=True,
            identity_rotation_interval=300,
            fullauto_max_urls=1000,
            fullauto_max_time=300
        )

    @pytest.fixture
    def attack_config_slowloris(self):
        """Create a slowloris mode AttackConfig."""
        return AttackConfig(
            mode='slowloris',
            target='https://example.com',
            num_threads=50,
            http_method='GET',
            cache_buster=True,
            identity_rotation_interval=60,
            slowloris_num_sockets=200
        )

    # =====================================================================
    # Successful Validation Tests
    # =====================================================================

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_success_all_checks_pass(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test validate returns True when all checks pass."""
        result = validator.validate(mock_tor_client, attack_config_singleshot)
        
        assert result is True
        mock_error.assert_not_called()

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_displays_exit_ip(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test that current Tor exit IP is displayed."""
        mock_tor_client.get_current_ip.return_value = '10.20.30.40'
        
        validator.validate(mock_tor_client, attack_config_singleshot)
        
        mock_log.assert_any_call('Current Tor exit IP: 10.20.30.40')

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_displays_config_summary(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test that configuration summary is displayed."""
        validator.validate(mock_tor_client, attack_config_singleshot)
        
        # Verify system() was called with config details
        mock_system.assert_any_call('Configuration:')
        mock_system.assert_any_call('  Mode: singleshot')
        mock_system.assert_any_call(f"  Target: {attack_config_singleshot.target}")
        mock_system.assert_any_call(f"  Threads: {attack_config_singleshot.num_threads}")
        mock_system.assert_any_call(f"  HTTP Method: {attack_config_singleshot.http_method}")
        mock_system.assert_any_call(f"  Cache Buster: {attack_config_singleshot.cache_buster}")

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_enters_proxy_scope(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test that proxy_scope context manager is entered."""
        validator.validate(mock_tor_client, attack_config_singleshot)
        
        # Verify proxy_scope was called
        mock_tor_client.proxy_scope.assert_called_once()

    # =====================================================================
    # Failure Tests
    # =====================================================================

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_fails_tor_not_connected(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test validate returns False when Tor is not connected."""
        mock_tor_client._is_connected = False
        
        result = validator.validate(mock_tor_client, attack_config_singleshot)
        
        assert result is False
        mock_error.assert_called_once()
        assert 'not connected' in mock_error.call_args[0][0].lower()

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_fails_proxy_connection(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test validate returns False when proxy connection fails."""
        # Create a proxy_scope that raises ConnectionErrorException
        def raise_connection_error(*args, **kwargs):
            raise ConnectionErrorException("proxy connection failed")
        
        mock_tor_client.proxy_scope.side_effect = raise_connection_error
        
        result = validator.validate(mock_tor_client, attack_config_singleshot)
        
        assert result is False
        mock_error.assert_called_once()

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_fails_generic_exception(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test validate returns False on unexpected exception."""
        mock_tor_client.get_current_ip.side_effect = Exception("unexpected error")
        
        result = validator.validate(mock_tor_client, attack_config_singleshot)
        
        assert result is False
        mock_error.assert_called_once()

    # =====================================================================
    # Configuration Display Tests
    # =====================================================================

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_displays_mode_specific_options_slowloris(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_slowloris
    ):
        """Test that slowloris-specific options are displayed."""
        validator.validate(mock_tor_client, attack_config_slowloris)
        
        mock_system.assert_any_call('  Mode: slowloris')
        mock_system.assert_any_call(f"  Sockets per Thread: {attack_config_slowloris.slowloris_num_sockets}")

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_displays_mode_specific_options_fullauto(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_fullauto
    ):
        """Test that fullauto-specific options are displayed."""
        validator.validate(mock_tor_client, attack_config_fullauto)
        
        mock_system.assert_any_call('  Mode: fullauto')
        mock_system.assert_any_call(f"  Max URLs: {attack_config_fullauto.fullauto_max_urls}")
        mock_system.assert_any_call(f"  Max Time: {attack_config_fullauto.fullauto_max_time} seconds")

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_displays_identity_rotation_disabled(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_singleshot
    ):
        """Test that 'Disabled' is shown when identity_rotation_interval is None."""
        validator.validate(mock_tor_client, attack_config_singleshot)
        
        mock_system.assert_any_call('  Identity Rotation: Disabled')

    @patch('app.preflight.app.console.log')
    @patch('app.preflight.app.console.system')
    @patch('app.preflight.app.console.error')
    def test_validate_displays_identity_rotation_enabled(
        self, mock_error, mock_system, mock_log, validator, mock_tor_client, attack_config_fullauto
    ):
        """Test that interval is shown when identity_rotation_interval is configured."""
        validator.validate(mock_tor_client, attack_config_fullauto)
        
        mock_system.assert_any_call(f"  Identity Rotation: {attack_config_fullauto.identity_rotation_interval} seconds")
