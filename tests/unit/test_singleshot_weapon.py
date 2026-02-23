"""Comprehensive unit tests for the SingleShotWeapon class.

This module provides complete test coverage for the SingleShotWeapon class including:
- Initialization with correct defaults and parameters
- Successful attack execution with proper AttackResult population
- Error handling for RequestException and generic exceptions
- Byte tracking accuracy
- Response time calculations
- HTTP method variations
- Cache buster functionality

All external dependencies (NetworkClient, app.net functions, time) are mocked
to ensure isolated unit tests that don't require actual network connections.
"""

import pytest
import time
from unittest.mock import MagicMock, patch, Mock
from app.models import AttackResult
from app.weapons.singleshot import SingleShotWeapon
from app.net import NetworkClient, RequestException


class TestSingleShotWeaponInitialization:
    """Test cases for SingleShotWeapon initialization."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SingleShotWeapon instance for each test."""
        return SingleShotWeapon()

    @pytest.fixture
    def mock_network_client(self):
        """Mock NetworkClient with common return values."""
        mock_client = MagicMock()
        mock_client.request.return_value = (MagicMock(), 100, 200)
        return mock_client

    def test_weapon_initializes_with_default_http_method(self, weapon):
        """Test weapon initializes with correct http_method (default 'GET')."""
        assert weapon._http_method == 'GET'

    def test_weapon_initializes_with_default_cache_buster(self, weapon):
        """Test weapon initializes with correct cache_buster (default False)."""
        assert weapon._cache_buster is False

    def test_weapon_initializes_with_custom_http_method(self):
        """Test weapon initializes with custom HTTP method."""
        weapon = SingleShotWeapon(http_method='POST')
        assert weapon._http_method == 'POST'

    def test_weapon_initializes_with_custom_cache_buster(self):
        """Test weapon initializes with custom cache_buster setting."""
        weapon = SingleShotWeapon(cache_buster=True)
        assert weapon._cache_buster is True

    @patch('app.weapons.singleshot.NetworkClient')
    def test_network_client_instance_is_created(self, mock_network_client_class):
        """Test NetworkClient instance is created during initialization."""
        SingleShotWeapon()
        mock_network_client_class.assert_called_once()

    @patch('app.weapons.singleshot.NetworkClient')
    def test_rotate_user_agent_is_called_during_initialization(self, mock_network_client_class):
        """Test rotate_user_agent() is called during initialization."""
        mock_client = MagicMock()
        mock_network_client_class.return_value = mock_client

        SingleShotWeapon()

        mock_client.rotate_user_agent.assert_called_once()


class TestSingleShotWeaponSuccessPath:
    """Test cases for SingleShotWeapon successful attack execution."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SingleShotWeapon instance for each test."""
        return SingleShotWeapon()

    @pytest.fixture
    def mock_response(self):
        """Mock HTTP response object."""
        response = MagicMock()
        response.getcode.return_value = 200
        return response

    def test_attack_returns_attackresult_with_num_hits_1_on_success(self, weapon):
        """Test attack() returns AttackResult with num_hits=1 on success."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.num_hits == 1

    def test_http_status_is_set_from_response_code_200(self, weapon):
        """Test http_status is set from response code (200)."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.http_status == 200

    def test_http_status_is_set_from_response_code_404(self, weapon):
        """Test http_status is set from response code (404)."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 404

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.http_status == 404

    def test_http_status_is_set_from_response_code_500(self, weapon):
        """Test http_status is set from response code (500)."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 500

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.http_status == 500

    def test_bytes_sent_is_populated_from_network_client(self, weapon):
        """Test bytes_sent is populated from NetworkClient.request() return value."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 150, 250)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_sent == 150

    def test_bytes_received_is_populated_from_network_client(self, weapon):
        """Test bytes_received is populated from NetworkClient.request() return value."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 150, 250)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_received == 250

    def test_response_time_ms_is_calculated_correctly(self, weapon):
        """Test response_time_ms is calculated correctly using time.time() delta."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.time') as mock_time:
            mock_time.time.side_effect = [1000.0, 1001.5]  # 1.5 seconds elapsed

            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                    result = weapon.attack()

        assert result.response_time_ms == 1500.0  # 1.5 seconds = 1500ms

    def test_errors_is_0_on_successful_request(self, weapon):
        """Test errors=0 on successful request."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.errors == 0

    def test_url_ensure_valid_is_called_on_target_url(self, weapon):
        """Test url_ensure_valid() is called on target URL."""
        weapon._target_url = 'example.com'

        with patch('app.net.url_ensure_valid', return_value='https://example.com') as mock_url_ensure:
            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.getcode.return_value = 200
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                weapon.attack()

        mock_url_ensure.assert_called_once_with('example.com')

    def test_url_cache_buster_is_called_when_cache_buster_true(self, weapon):
        """Test url_cache_buster() is called when cache_buster=True."""
        weapon._target_url = 'https://example.com'
        weapon._cache_buster = True

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.net.url_cache_buster', return_value='https://example.com?123') as mock_cache_buster:
                with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                    mock_client = MagicMock()
                    mock_response = MagicMock()
                    mock_response.getcode.return_value = 200
                    mock_client.request.return_value = (mock_response, 100, 200)
                    mock_client_class.return_value = mock_client
                    weapon._network_client = mock_client  # Replace real client with mock

                    weapon.attack()

        mock_cache_buster.assert_called_once_with('https://example.com')

    def test_url_cache_buster_is_not_called_when_cache_buster_false(self, weapon):
        """Test url_cache_buster() is NOT called when cache_buster=False."""
        weapon._target_url = 'https://example.com'
        weapon._cache_buster = False

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.net.url_cache_buster') as mock_cache_buster:
                with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                    mock_client = MagicMock()
                    mock_response = MagicMock()
                    mock_response.getcode.return_value = 200
                    mock_client.request.return_value = (mock_response, 100, 200)
                    mock_client_class.return_value = mock_client
                    weapon._network_client = mock_client  # Replace real client with mock

                    weapon.attack()

        mock_cache_buster.assert_not_called()


class TestSingleShotWeaponErrorHandling:
    """Test cases for SingleShotWeapon error handling."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SingleShotWeapon instance for each test."""
        return SingleShotWeapon()

    def test_requestexception_returns_attackresult_with_errors_1(self, weapon):
        """Test RequestException returns AttackResult with errors=1."""
        weapon._target_url = 'https://example.com'

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.side_effect = RequestException("Request failed")
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.errors == 1

    def test_requestexception_sets_http_status_none(self, weapon):
        """Test RequestException sets http_status=None."""
        weapon._target_url = 'https://example.com'

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.side_effect = RequestException("Request failed")
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                result = weapon.attack()

        assert result.http_status is None

    def test_requestexception_sets_num_hits_0(self, weapon):
        """Test RequestException sets num_hits=0."""
        weapon._target_url = 'https://example.com'

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.side_effect = RequestException("Request failed")
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                result = weapon.attack()

        assert result.num_hits == 0

    def test_generic_exception_returns_attackresult_with_errors_1(self, weapon):
        """Test generic Exception returns AttackResult with errors=1."""
        weapon._target_url = 'https://example.com'

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.side_effect = Exception("Unexpected error")
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.errors == 1

    def test_generic_exception_sets_http_status_none(self, weapon):
        """Test generic Exception sets http_status=None."""
        weapon._target_url = 'https://example.com'

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.side_effect = Exception("Unexpected error")
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                result = weapon.attack()

        assert result.http_status is None


class TestSingleShotWeaponByteTracking:
    """Test cases for SingleShotWeapon byte tracking."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SingleShotWeapon instance for each test."""
        return SingleShotWeapon()

    def test_bytes_sent_0(self, weapon):
        """Test bytes_sent=0 is tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 0, 0)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_sent == 0

    def test_bytes_sent_100(self, weapon):
        """Test bytes_sent=100 is tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_sent == 100

    def test_bytes_sent_1000(self, weapon):
        """Test bytes_sent=1000 is tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 1000, 2000)
            mock_client_class.return_value = mock_client

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_sent == 1000

    def test_bytes_sent_large_value(self, weapon):
        """Test large bytes_sent values are tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        large_value = 1000000

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, large_value, large_value * 2)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_sent == large_value

    def test_bytes_received_0(self, weapon):
        """Test bytes_received=0 is tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 0)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_received == 0

    def test_bytes_received_100(self, weapon):
        """Test bytes_received=100 is tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 50, 100)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_received == 100

    def test_bytes_received_1000(self, weapon):
        """Test bytes_received=1000 is tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 500, 1000)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_received == 1000

    def test_bytes_received_large_value(self, weapon):
        """Test large bytes_received values are tracked correctly."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        large_value = 1000000

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, large_value // 2, large_value)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon.attack()

        assert result.bytes_received == large_value


class TestSingleShotWeaponResponseTime:
    """Test cases for SingleShotWeapon response time calculations."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SingleShotWeapon instance for each test."""
        return SingleShotWeapon()

    def test_response_time_calculation_with_mocked_time(self, weapon):
        """Test response time calculation with mocked time values."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.time') as mock_time:
            mock_time.time.side_effect = [1000.0, 1001.0]  # 1 second elapsed

            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                    result = weapon.attack()

        assert result.response_time_ms == 1000.0  # 1 second = 1000ms

    def test_response_time_is_in_milliseconds(self, weapon):
        """Test response time is in milliseconds."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.time') as mock_time:
            mock_time.time.side_effect = [1000.0, 1000.5]  # 0.5 seconds elapsed

            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                    result = weapon.attack()

        assert result.response_time_ms == 500.0  # 0.5 seconds = 500ms

    def test_response_time_for_fast_requests_under_1ms(self, weapon):
        """Test response time for fast requests (< 1ms)."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.time') as mock_time:
            mock_time.time.side_effect = [1000.0, 1000.0005]  # 0.5ms elapsed

            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                    result = weapon.attack()

        assert result.response_time_ms == 0.5

    def test_response_time_for_slow_requests_over_1000ms(self, weapon):
        """Test response time for slow requests (> 1000ms)."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.time') as mock_time:
            mock_time.time.side_effect = [1000.0, 1002.5]  # 2.5 seconds elapsed

            with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                    result = weapon.attack()

        assert result.response_time_ms == 2500.0


class TestSingleShotWeaponHttpMethods:
    """Test cases for SingleShotWeapon with different HTTP methods."""

    @pytest.fixture
    def weapon(self):
        """Create fresh SingleShotWeapon instance for each test."""
        return SingleShotWeapon()

    def test_get_method_passed_to_network_client(self, weapon):
        """Test GET method is passed to NetworkClient.request()."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'GET'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.attack()

            mock_client.request.assert_called_once_with('GET', 'https://example.com')

    def test_post_method_passed_to_network_client(self, weapon):
        """Test POST method is passed to NetworkClient.request()."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'POST'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.attack()

            mock_client.request.assert_called_once_with('POST', 'https://example.com')

    def test_put_method_passed_to_network_client(self, weapon):
        """Test PUT method is passed to NetworkClient.request()."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'PUT'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.attack()

            mock_client.request.assert_called_once_with('PUT', 'https://example.com')

    def test_delete_method_passed_to_network_client(self, weapon):
        """Test DELETE method is passed to NetworkClient.request()."""
        weapon._target_url = 'https://example.com'
        weapon._http_method = 'DELETE'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200

        with patch('app.weapons.singleshot.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.attack()

            mock_client.request.assert_called_once_with('DELETE', 'https://example.com')
