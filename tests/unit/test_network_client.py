"""Comprehensive unit tests for the NetworkClient class.

This module provides complete test coverage for the NetworkClient class including:
- User agent rotation (rotate_user_agent, get_user_agent)
- HTTP request handling (request)
- IP lookup (lookup_ip)
- Byte tracking calculations
- Error handling and edge cases
- Module-level utility functions (url_ensure_valid, url_cache_buster)
- Module-level singleton wrapper functions

All external dependencies (user_agent, urllib) are mocked to ensure
isolated unit tests that don't require actual network connections.
"""

import random
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import urllib.error
import urllib.request

from app.net import (
    NetworkClient,
    RequestException,
    url_ensure_valid,
    url_cache_buster,
)


class TestNetworkClient:
    """Test class for NetworkClient covering all public methods and edge cases."""

    @pytest.fixture
    def network_client(self):
        """Create a fresh NetworkClient instance for each test."""
        return NetworkClient()

    @pytest.fixture
    def mock_user_agent(self):
        """Mock user agent string."""
        return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

    @pytest.fixture
    def mock_response(self):
        """Create a mock urllib response object with headers and methods."""
        response = MagicMock()
        response.getcode.return_value = 200
        response.read.return_value = b'Test response content'
        response.headers = {'Content-Length': '23'}
        response.length = 23
        return response

    # =========================================================================
    # Tests for rotate_user_agent() method
    # =========================================================================

    def test_rotate_user_agent_generates_with_correct_os(self, network_client):
        """Test that user agent is generated with correct OS parameters ('mac', 'win')."""
        with patch('app.net.user_agent.generate_user_agent', return_value='test_ua') as mock_generate:
            network_client.rotate_user_agent()

            mock_generate.assert_called_once_with(os=('mac', 'win'))

    def test_rotate_user_agent_sets_user_agent(self, network_client):
        """Test that _user_agent is set after rotation."""
        test_ua = 'Mozilla/5.0 Test User Agent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        assert network_client._user_agent == test_ua

    def test_rotate_user_agent_called_correctly(self, network_client):
        """Test that user_agent.generate_user_agent is called correctly."""
        with patch('app.net.user_agent.generate_user_agent', return_value='test_ua') as mock_generate:
            network_client.rotate_user_agent()

            # Verify the function was called with correct parameters
            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args[1]
            assert call_kwargs['os'] == ('mac', 'win')

    # =========================================================================
    # Tests for get_user_agent() method
    # =========================================================================

    def test_get_user_agent_returns_none_when_not_set(self, network_client):
        """Test returns None when user agent not set."""
        result = network_client.get_user_agent()

        assert result is None

    def test_get_user_agent_returns_string_after_rotation(self, network_client, mock_user_agent):
        """Test returns user agent string after rotation."""
        with patch('app.net.user_agent.generate_user_agent', return_value=mock_user_agent):
            network_client.rotate_user_agent()

        result = network_client.get_user_agent()

        assert result == mock_user_agent

    def test_get_user_agent_returns_same_until_rotated(self, network_client):
        """Test returns the same user agent until rotated again."""
        first_ua = 'First User Agent'
        second_ua = 'Second User Agent'

        with patch('app.net.user_agent.generate_user_agent', return_value=first_ua):
            network_client.rotate_user_agent()

        first_result = network_client.get_user_agent()

        # Get again without rotating
        second_result = network_client.get_user_agent()

        assert first_result == second_result == first_ua

        # Now rotate again
        with patch('app.net.user_agent.generate_user_agent', return_value=second_ua):
            network_client.rotate_user_agent()

        third_result = network_client.get_user_agent()

        assert third_result == second_ua
        assert third_result != first_ua

    # =========================================================================
    # Tests for request() method
    # =========================================================================

    def test_request_success_get_returns_tuple(self, network_client, mock_response):
        """Test successful GET request returns (response, bytes_sent, bytes_received)."""
        test_ua = 'Test User Agent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        with patch('app.net.urllib.request.Request') as mock_request_class:
            with patch('app.net.urllib.request.urlopen', return_value=mock_response):
                result = network_client.request('GET', 'https://example.com')

        assert isinstance(result, tuple)
        assert len(result) == 3
        response, bytes_sent, bytes_received = result
        assert response == mock_response
        assert isinstance(bytes_sent, int)
        assert isinstance(bytes_received, int)

    def test_request_success_post_returns_tuple(self, network_client, mock_response):
        """Test successful POST request returns correct tuple."""
        test_ua = 'Test User Agent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        with patch('app.net.urllib.request.Request') as mock_request_class:
            with patch('app.net.urllib.request.urlopen', return_value=mock_response):
                result = network_client.request('POST', 'https://example.com')

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_request_without_user_agent_raises(self, network_client):
        """Test request without user agent raises RequestException."""
        with pytest.raises(RequestException) as exc_info:
            network_client.request('GET', 'https://example.com')

        assert "no user agent set; call rotate_user_agent() first" in str(exc_info.value)

    def test_request_bytes_sent_includes_method_url_and_separators(self, network_client):
        """Test bytes_sent calculation includes method, URL, headers, and separators."""
        test_ua = 'TestUserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b''
        mock_response.headers = {}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, bytes_sent, _ = network_client.request('GET', 'http://test.com')

        # Calculate expected: len('GET') + len('http://test.com') + len(' HTTP/1.1\r\n')
        # + len('User-Agent') + len(': ') + len(test_ua) + len('\r\n')
        # + len('\r\n') for header/body separator
        expected = (
            len('GET') +
            len('http://test.com') +
            len(' HTTP/1.1\r\n') +
            len('User-Agent') + len(': ') + len(test_ua) + len('\r\n') +
            len('\r\n')
        )

        assert bytes_sent == expected

    def test_request_bytes_received_uses_content_length(self, network_client):
        """Test bytes_received calculation uses Content-Length header when available."""
        test_ua = 'TestUserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers = {'Content-Length': '1000'}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, _, bytes_received = network_client.request('GET', 'http://test.com')

        # Expected: 200 (estimated headers) + 1000 (Content-Length)
        assert bytes_received == 1200

    def test_request_bytes_received_estimation_without_content_length(self, network_client):
        """Test bytes_received estimation when Content-Length is missing."""
        test_ua = 'TestUserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers = {}  # No Content-Length
        mock_response.length = 500

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, _, bytes_received = network_client.request('GET', 'http://test.com')

        # Expected: 200 (estimated headers) + 500 (length hint)
        assert bytes_received == 700

    def test_request_httperror_caught_and_returned(self, network_client):
        """Test HTTPError is caught and returned as response with error tracking."""
        test_ua = 'TestUserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_error = urllib.error.HTTPError(
            url='https://example.com',
            code=404,
            msg='Not Found',
            hdrs={'Content-Length': '100'},
            fp=None
        )

        with patch('app.net.urllib.request.urlopen', side_effect=mock_error):
            response, bytes_sent, bytes_received = network_client.request('GET', 'https://example.com')

        # HTTPError should be returned as the response
        assert response is mock_error
        # Bytes received should still be tracked
        assert bytes_received == 300  # 200 headers + 100 Content-Length

    def test_request_httperror_tracks_bytes_received(self, network_client):
        """Test that HTTPError still tracks bytes_received."""
        test_ua = 'TestUserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_error = urllib.error.HTTPError(
            url='https://example.com',
            code=500,
            msg='Server Error',
            hdrs={'Content-Length': '200'},
            fp=None
        )

        with patch('app.net.urllib.request.urlopen', side_effect=mock_error):
            _, _, bytes_received = network_client.request('GET', 'https://example.com')

        assert bytes_received == 400  # 200 headers + 200 Content-Length

    def test_request_generic_exception_raises_request_exception(self, network_client):
        """Test generic exceptions raise RequestException."""
        test_ua = 'TestUserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        with patch('app.net.urllib.request.urlopen', side_effect=Exception("Network timeout")):
            with pytest.raises(RequestException) as exc_info:
                network_client.request('GET', 'https://example.com')

            assert "Network timeout" in str(exc_info.value)

    def test_request_user_agent_header_set_correctly(self, network_client):
        """Verify User-Agent header is set correctly in request."""
        test_ua = 'TestUserAgent123'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_request = MagicMock()

        with patch('app.net.urllib.request.Request', return_value=mock_request) as mock_request_class:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.headers = {}

            with patch('app.net.urllib.request.urlopen', return_value=mock_response):
                network_client.request('GET', 'https://example.com')

            # Verify Request was created with correct User-Agent header
            call_args = mock_request_class.call_args
            headers = call_args[1].get('headers', {})
            assert headers.get('User-Agent') == test_ua

    # =========================================================================
    # Tests for lookup_ip() method
    # =========================================================================

    def test_lookup_ip_success(self, network_client):
        """Test successful IP lookup returns IP string."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'192.168.1.100\n'

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            ip = network_client.lookup_ip()

        assert ip == '192.168.1.100'

    def test_lookup_ip_failure_raises_request_exception(self, network_client):
        """Test IP lookup failure raises RequestException."""
        with patch('app.net.urllib.request.urlopen', side_effect=Exception("DNS error")):
            with pytest.raises(RequestException) as exc_info:
                network_client.lookup_ip()

            assert "failed to lookup IP" in str(exc_info.value)
            assert "DNS error" in str(exc_info.value)

    def test_lookup_ip_decodes_and_strips_newline(self, network_client):
        """Test that response is decoded and newline is stripped."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'10.0.0.1\n'

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            ip = network_client.lookup_ip()

        assert ip == '10.0.0.1'

    # =========================================================================
    # Tests for byte tracking
    # =========================================================================

    def test_bytes_sent_includes_request_line(self, network_client):
        """Test bytes_sent includes request line (method + URL + HTTP version)."""
        test_ua = 'UA'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, bytes_sent, _ = network_client.request('GET', 'http://a.com')

        # Verify request line is included
        expected_request_line = len('GET') + len('http://a.com') + len(' HTTP/1.1\r\n')
        assert bytes_sent >= expected_request_line

    def test_bytes_sent_includes_headers(self, network_client):
        """Test bytes_sent includes all headers with proper formatting."""
        test_ua = 'UserAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, bytes_sent, _ = network_client.request('GET', 'http://test.com')

        # Header format: "Key: Value\r\n"
        expected_header = len('User-Agent') + len(': ') + len(test_ua) + len('\r\n')
        assert bytes_sent >= expected_header

    def test_bytes_sent_includes_separator(self, network_client):
        """Test bytes_sent includes header/body separator."""
        test_ua = 'UA'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, bytes_sent, _ = network_client.request('GET', 'http://a.com')

        # Header/body separator is '\r\n' (2 bytes)
        assert bytes_sent >= 2

    def test_bytes_received_includes_estimated_header_size(self, network_client):
        """Test bytes_received includes estimated header size (200 bytes)."""
        test_ua = 'UA'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {}  # No Content-Length

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, _, bytes_received = network_client.request('GET', 'http://a.com')

        # Should include at least 200 bytes for headers
        assert bytes_received >= 200

    def test_bytes_received_includes_content_length(self, network_client):
        """Test bytes_received includes Content-Length when present."""
        test_ua = 'UA'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {'Content-Length': '500'}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, _, bytes_received = network_client.request('GET', 'http://a.com')

        # Should be 200 (headers) + 500 (Content-Length)
        assert bytes_received == 700

    def test_bytes_received_uses_length_hint(self, network_client):
        """Test bytes_received uses length hint when Content-Length missing."""
        test_ua = 'UA'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {}  # No Content-Length
        mock_response.length = 300

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, _, bytes_received = network_client.request('GET', 'http://a.com')

        # Should be 200 (headers) + 300 (length hint)
        assert bytes_received == 500

    def test_bytes_received_header_only_when_no_content_length_or_length(self, network_client):
        """Test bytes_received equals 200 when Content-Length and length hint are absent."""
        test_ua = 'TestAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {}  # No Content-Length
        # No length attribute set (MagicMock returns None for undefined attributes)

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, _, bytes_received = network_client.request('GET', 'http://example.com')

        # Should be 200 (headers only) when both Content-Length and length hint are absent
        assert bytes_received == 200

    def test_bytes_calculation_known_request(self, network_client):
        """Create test with known request to verify byte calculation accuracy."""
        test_ua = 'TestAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_response = MagicMock()
        mock_response.headers = {'Content-Length': '100'}

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            _, bytes_sent, bytes_received = network_client.request('GET', 'http://example.com')

        # Calculate expected bytes_sent
        # Request line: "GET http://example.com HTTP/1.1\r\n"
        # Headers: "User-Agent: TestAgent\r\n"
        # Separator: "\r\n"
        expected_sent = (
            len('GET') + len('http://example.com') + len(' HTTP/1.1\r\n') +
            len('User-Agent') + len(': ') + len('TestAgent') + len('\r\n') +
            len('\r\n')
        )

        expected_received = 200 + 100  # Headers + Content-Length

        assert bytes_sent == expected_sent
        assert bytes_received == expected_received

    # =========================================================================
    # Tests for error handling
    # =========================================================================

    def test_error_user_agent_not_set(self, network_client):
        """Test RequestException raised when user agent not set."""
        with pytest.raises(RequestException) as exc_info:
            network_client.request('GET', 'https://example.com')

        assert "no user agent set" in str(exc_info.value)

    def test_error_network_errors(self, network_client):
        """Test RequestException raised on network errors."""
        test_ua = 'TestAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        with patch('app.net.urllib.request.urlopen', side_effect=Exception("Connection refused")):
            with pytest.raises(RequestException) as exc_info:
                network_client.request('GET', 'https://example.com')

            assert "Connection refused" in str(exc_info.value)

    def test_error_message_includes_original_error(self, network_client):
        """Test RequestException message includes original error details."""
        test_ua = 'TestAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        original_error = "DNS resolution failed"

        with patch('app.net.urllib.request.urlopen', side_effect=Exception(original_error)):
            with pytest.raises(RequestException) as exc_info:
                network_client.request('GET', 'https://example.com')

            assert original_error in str(exc_info.value)

    def test_httperror_handled_gracefully(self, network_client):
        """Test HTTPError is handled gracefully and returned as response."""
        test_ua = 'TestAgent'

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            network_client.rotate_user_agent()

        mock_error = urllib.error.HTTPError(
            url='https://example.com',
            code=404,
            msg='Not Found',
            hdrs=None,
            fp=None
        )

        with patch('app.net.urllib.request.urlopen', side_effect=mock_error):
            response, _, _ = network_client.request('GET', 'https://example.com')

        # Should return the HTTPError as the response, not raise it
        assert response is mock_error


class TestUrlEnsureValid:
    """Tests for url_ensure_valid() utility function."""

    def test_url_without_scheme_gets_https(self):
        """Test URL without scheme gets https:// prefix."""
        result = url_ensure_valid('example.com')
        assert result == 'https://example.com'

    def test_url_with_http_preserved(self):
        """Test URL with http:// scheme is preserved."""
        result = url_ensure_valid('http://example.com')
        assert result == 'http://example.com'

    def test_url_with_https_preserved(self):
        """Test URL with https:// scheme is preserved."""
        result = url_ensure_valid('https://example.com')
        assert result == 'https://example.com'

    def test_url_without_netloc_parsed_correctly(self):
        """Test URL without netloc is properly parsed."""
        result = url_ensure_valid('example.com/path')
        assert result == 'https://example.com/path'

    def test_url_preserves_path(self):
        """Test URL with path is preserved."""
        result = url_ensure_valid('example.com/some/path')
        assert result == 'https://example.com/some/path'

    def test_url_preserves_query(self):
        """Test URL with query parameters is preserved."""
        result = url_ensure_valid('example.com?key=value')
        assert result == 'https://example.com?key=value'

    def test_url_preserves_fragment(self):
        """Test URL with fragment is preserved."""
        result = url_ensure_valid('example.com#section')
        assert result == 'https://example.com#section'

    def test_url_preserves_all_components(self):
        """Test URL with path, params, query, fragment are preserved."""
        result = url_ensure_valid('example.com/path;params?query=1#frag')
        assert result == 'https://example.com/path;params?query=1#frag'


class TestUrlCacheBuster:
    """Tests for url_cache_buster() utility function."""

    def test_adds_random_query_param(self):
        """Test that random query parameter is added."""
        result = url_cache_buster('https://example.com')

        # Result should contain a query string
        assert '?' in result

    def test_replaces_existing_query_params(self):
        """Test that existing query parameters are replaced."""
        result = url_cache_buster('https://example.com?old=value')

        # Should have new query parameter
        assert '?' in result
        # Should not contain the old parameter name
        assert 'old=' not in result

    def test_preserves_scheme_netloc_path(self):
        """Test that scheme, netloc, path are preserved."""
        result = url_cache_buster('https://example.com/path')

        assert result.startswith('https://example.com/path')

    def test_random_number_within_range(self):
        """Test that random number is within expected range (1-999999999)."""
        with patch('app.net.random.randint') as mock_randint:
            mock_randint.return_value = 12345

            result = url_cache_buster('https://example.com')

            # Verify randint was called with correct range
            mock_randint.assert_called_once_with(1, 999999999)
            assert '?12345' in result

    def test_preserves_params_and_fragment(self):
        """Test that params and fragment are preserved."""
        result = url_cache_buster('https://example.com/path;params#fragment')

        # Should preserve params and fragment
        assert ';params' in result
        assert '#fragment' in result


class TestNetworkClientSingletonFunctions:
    """Tests for module-level singleton wrapper functions."""

    def test_new_user_agent_creates_singleton(self):
        """Test that new_user_agent() creates module-level singleton."""
        import app.net as net_module

        # Reset singleton
        net_module._network_client = None

        with patch('app.net.user_agent.generate_user_agent', return_value='test_ua'):
            net_module.new_user_agent()

            assert net_module._network_client is not None
            assert isinstance(net_module._network_client, NetworkClient)

        # Cleanup
        net_module._network_client = None

    def test_get_user_agent_returns_singleton_value(self):
        """Test that get_user_agent() returns value from singleton."""
        import app.net as net_module

        # Reset singleton
        net_module._network_client = None

        with patch('app.net.user_agent.generate_user_agent', return_value='test_ua'):
            net_module.new_user_agent()
            result = net_module.get_user_agent()

            assert result == 'test_ua'

        # Cleanup
        net_module._network_client = None

    def test_request_uses_singleton(self):
        """Test that request() uses singleton NetworkClient."""
        import app.net as net_module

        # Reset singleton
        net_module._network_client = None

        test_ua = 'TestUserAgent'
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers = {}

        with patch('app.net.user_agent.generate_user_agent', return_value=test_ua):
            with patch('app.net.urllib.request.urlopen', return_value=mock_response):
                result = net_module.request('GET', 'https://example.com')

                # Should return response from singleton
                assert result == mock_response

        # Cleanup
        net_module._network_client = None

    def test_lookupip_uses_singleton(self):
        """Test that lookupip() uses singleton NetworkClient."""
        import app.net as net_module

        # Reset singleton
        net_module._network_client = None

        mock_response = MagicMock()
        mock_response.read.return_value = b'192.168.1.1\n'

        with patch('app.net.urllib.request.urlopen', return_value=mock_response):
            result = net_module.lookupip()

            assert result == '192.168.1.1'

        # Cleanup
        net_module._network_client = None


class TestNetworkClientInitialization:
    """Tests for NetworkClient initialization."""

    def test_default_user_agent_none(self):
        """Test that NetworkClient initializes with _user_agent as None."""
        client = NetworkClient()
        assert client._user_agent is None
