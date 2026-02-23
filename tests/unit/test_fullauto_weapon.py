"""Comprehensive unit tests for the FullAutoWeapon class.

This module provides complete test coverage for the FullAutoWeapon class including:
- Initialization with correct defaults and parameters
- URL targeting and discovery (crawling links)
- Successful attack execution with proper AttackResult population
- Error handling for exceptions
- Byte tracking accuracy during crawling
- Response time calculations
- URL management (duplicates, cross-domain filtering)
- BeautifulSoup HTML parsing
- Random URL selection

All external dependencies (NetworkClient, BeautifulSoup, random, app.net functions) are mocked
to ensure isolated unit tests that don't require actual network connections.
"""

import pytest
import time
import random
from unittest.mock import MagicMock, patch, Mock
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.models import AttackResult
from app.weapons.fullauto import FullAutoWeapon
from app.net import NetworkClient, RequestException


class TestFullAutoWeaponInitialization:
    """Test cases for FullAutoWeapon initialization."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_weapon_initializes_with_empty_urls_list(self, weapon):
        """Test weapon initializes with empty _urls list."""
        assert weapon._urls == []

    @patch('app.weapons.fullauto.NetworkClient')
    def test_network_client_instance_is_created(self, mock_network_client_class):
        """Test NetworkClient instance is created during initialization."""
        FullAutoWeapon()
        mock_network_client_class.assert_called_once()

    @patch('app.weapons.fullauto.NetworkClient')
    def test_rotate_user_agent_is_called_during_initialization(self, mock_network_client_class):
        """Test rotate_user_agent() is called during initialization."""
        mock_client = MagicMock()
        mock_network_client_class.return_value = mock_client

        FullAutoWeapon()

        mock_client.rotate_user_agent.assert_called_once()


class TestFullAutoWeaponTargetMethod:
    """Test cases for FullAutoWeapon target() method."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_target_adds_url_to_urls_list(self, weapon):
        """Test target() adds URL to _urls list."""
        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            weapon.target('https://example.com')

        assert len(weapon._urls) == 1
        assert weapon._urls[0] == 'https://example.com'

    def test_target_calls_url_ensure_valid_on_target_url(self, weapon):
        """Test target() calls url_ensure_valid() on target URL."""
        with patch('app.net.url_ensure_valid', return_value='https://example.com') as mock_url_ensure:
            weapon.target('example.com')

        mock_url_ensure.assert_called_once_with('example.com')

    def test_first_url_in_list_is_target_url(self, weapon):
        """Test first URL in list is the target URL."""
        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            weapon.target('https://example.com')

        assert weapon._urls[0] == 'https://example.com'


class TestFullAutoWeaponUrlDiscovery:
    """Test cases for FullAutoWeapon URL discovery and _add_url() method."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_add_url_resolves_relative_urls_correctly(self, weapon):
        """Test _add_url() resolves relative URLs correctly."""
        weapon._add_url(
            parent_url='https://example.com/path/',
            new_url='page.html'
        )

        assert 'https://example.com/path/page.html' in weapon._urls

    def test_add_url_only_adds_urls_from_same_domain(self, weapon):
        """Test _add_url() only adds URLs from same domain."""
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://other-domain.com/page'
        )

        # Should not add cross-domain URLs
        assert 'https://other-domain.com/page' not in weapon._urls

    def test_add_url_only_adds_http_https_urls(self, weapon):
        """Test _add_url() only adds HTTP/HTTPS URLs."""
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='ftp://example.com/file.txt'
        )

        # Should not add FTP URLs
        assert 'ftp://example.com/file.txt' not in weapon._urls

    def test_add_url_prevents_duplicate_urls(self, weapon):
        """Test _add_url() prevents duplicate URLs."""
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://example.com/page'
        )
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://example.com/page'
        )

        # Should only have one instance of the URL
        assert weapon._urls.count('https://example.com/page') == 1

    def test_add_url_handles_root_relative_urls(self, weapon):
        """Test _add_url() handles root-relative URLs."""
        weapon._add_url(
            parent_url='https://example.com/path/',
            new_url='/about'
        )

        assert 'https://example.com/about' in weapon._urls

    def test_add_url_handles_absolute_urls(self, weapon):
        """Test _add_url() handles absolute URLs."""
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://example.com/about'
        )

        assert 'https://example.com/about' in weapon._urls


class TestFullAutoWeaponHitMethod:
    """Test cases for FullAutoWeapon _hit() method."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_hit_parses_html_and_discovers_links(self, weapon):
        """Test _hit() parses HTML and discovers links."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        html_content = b'<html><body><a href="/page1">Link 1</a><a href="/page2">Link 2</a></body></html>'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = html_content
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon._hit('https://example.com')

        # Should have discovered the two links
        assert 'https://example.com/page1' in weapon._urls
        assert 'https://example.com/page2' in weapon._urls

    def test_hit_removes_non_html_urls_from_list(self, weapon):
        """Test _hit() removes non-HTML URLs from list."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com/file.pdf']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'PDF content'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'application/pdf'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com/file.pdf'):
                weapon._hit('https://example.com/file.pdf')

        # Should remove the non-HTML URL
        assert 'https://example.com/file.pdf' not in weapon._urls

    def test_hit_returns_tuple_of_status_and_bytes(self, weapon):
        """Test _hit() returns tuple of (status_code, bytes_sent, bytes_received)."""
        weapon._target_url = 'https://example.com'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML content'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 150, 250)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                result = weapon._hit('https://example.com')

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[0] == 200  # status_code
        assert result[1] == 150  # bytes_sent
        assert result[2] == 250  # bytes_received

    def test_hit_uses_cache_buster_when_enabled(self, weapon):
        """Test _hit() uses cache buster when enabled."""
        weapon._target_url = 'https://example.com'
        weapon._cache_buster = True

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.net.url_ensure_valid', return_value='https://example.com'):
            with patch('app.net.url_cache_buster', return_value='https://example.com?123') as mock_cache_buster:
                with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.request.return_value = (mock_response, 100, 200)
                    mock_client_class.return_value = mock_client
                    weapon._network_client = mock_client  # Replace real client with mock

                    weapon._hit('https://example.com')

        mock_cache_buster.assert_called_once_with('https://example.com')


class TestFullAutoWeaponAttackSuccessPath:
    """Test cases for FullAutoWeapon successful attack execution."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_attack_returns_attackresult_with_num_hits_1_on_success(self, weapon):
        """Test attack() returns AttackResult with num_hits=1 on success."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.num_hits == 1

    def test_attack_sets_http_status_from_response_code(self, weapon):
        """Test http_status is set from response code."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 404
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.http_status == 404

    def test_attack_populates_bytes_sent(self, weapon):
        """Test bytes_sent is populated from _hit() return value."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 150, 250)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.bytes_sent == 150

    def test_attack_populates_bytes_received(self, weapon):
        """Test bytes_received is populated from _hit() return value."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 150, 250)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.bytes_received == 250

    def test_attack_calculates_response_time_ms_correctly(self, weapon):
        """Test response_time_ms is calculated correctly."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.side_effect = [1000.0, 1001.5]  # 1.5 seconds elapsed

            with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client  # Replace real client with mock

                with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                    with patch('app.weapons.fullauto.random.randint', return_value=0):
                        result = weapon.attack()

        assert result.response_time_ms == 1500.0

    def test_attack_sets_errors_0_on_success(self, weapon):
        """Test errors=0 on successful request."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.errors == 0

    def test_attack_selects_random_url_from_urls_list(self, weapon):
        """Test random URL selection from _urls list."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com/page1', 'https://example.com/page2']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'HTML'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                mock_randint = MagicMock(return_value=1)
                with patch('app.weapons.fullauto.random.randint', mock_randint):
                    weapon.attack()

        # Verify random.randint was called with correct range
        mock_randint.assert_called_once_with(0, 1)


class TestFullAutoWeaponErrorHandling:
    """Test cases for FullAutoWeapon error handling."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_generic_exception_returns_attackresult_with_errors_1(self, weapon):
        """Test generic Exception returns AttackResult with errors=1."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.errors == 1

    def test_exception_sets_http_status_none(self, weapon):
        """Test exception sets http_status=None."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.http_status is None

    def test_exception_sets_num_hits_0(self, weapon):
        """Test exception sets num_hits=0."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.num_hits == 0

    def test_empty_urls_list_raises_indexerror(self, weapon):
        """Test empty _urls list raises IndexError and returns error result."""
        weapon._target_url = 'https://example.com'
        weapon._urls = []  # Empty list

        with patch('app.weapons.fullauto.random.randint', side_effect=IndexError("list index out of range")):
            result = weapon.attack()

        assert isinstance(result, AttackResult)
        assert result.errors == 1
        assert result.num_hits == 0
        assert result.http_status is None


class TestFullAutoWeaponByteTracking:
    """Test cases for FullAutoWeapon byte tracking during crawling."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_bytes_tracked_during_crawling(self, weapon):
        """Test bytes are tracked during crawling."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'<a href="/page">Link</a>'
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 500, 1000)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    result = weapon.attack()

        assert result.bytes_sent == 500
        assert result.bytes_received == 1000


class TestFullAutoWeaponUrlManagement:
    """Test cases for FullAutoWeapon URL list management."""

    @pytest.fixture
    def weapon(self):
        """Create fresh FullAutoWeapon instance for each test."""
        return FullAutoWeapon()

    def test_url_list_grows_as_links_are_discovered(self, weapon):
        """Test URL list grows as links are discovered."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        html_content = b'<html><body><a href="/page1">Link 1</a><a href="/page2">Link 2</a></body></html>'

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = html_content
        mock_info = MagicMock()
        mock_info.get_content_type.return_value = 'text/html'
        mock_response.info.return_value = mock_info

        with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.request.return_value = (mock_response, 100, 200)
            mock_client_class.return_value = mock_client
            weapon._network_client = mock_client  # Replace real client with mock

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    weapon.attack()

        # Should have grown to include discovered links
        assert len(weapon._urls) == 3  # original + 2 discovered

    def test_duplicate_urls_are_not_added(self, weapon):
        """Test duplicate URLs are not added."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        # Add same URL twice
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://example.com/page'
        )
        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://example.com/page'
        )

        assert weapon._urls.count('https://example.com/page') == 1

    def test_cross_domain_urls_are_filtered_out(self, weapon):
        """Test cross-domain URLs are filtered out."""
        weapon._target_url = 'https://example.com'
        weapon._urls = ['https://example.com']

        weapon._add_url(
            parent_url='https://example.com/',
            new_url='https://other-site.com/page'
        )

        assert 'https://other-site.com/page' not in weapon._urls


class TestFullAutoWeaponCrawlLimits:
    """Test cases for FullAutoWeapon crawl limit functionality."""

    @pytest.fixture
    def weapon_with_limits(self):
        """Create FullAutoWeapon instance with configurable limits for testing."""
        def _make_weapon(max_urls=500, max_time_seconds=180):
            return FullAutoWeapon(max_urls=max_urls, max_time_seconds=max_time_seconds)
        return _make_weapon

    def test_url_count_limit_stops_discovery_at_max_urls(self, weapon_with_limits):
        """Test URL count limit stops discovery when max_urls is reached."""
        weapon = weapon_with_limits(max_urls=5)

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.return_value = 1000.0  # Consistent time

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.target('https://example.com')

            # Simulate discovering 10 URLs
            for i in range(10):
                weapon._add_url(
                    parent_url='https://example.com/',
                    new_url=f'https://example.com/page{i}'
                )

        assert weapon._discovered_url_count == 5  # Limited to max_urls
        assert len(weapon._urls) == 5  # No more URLs added after limit
        assert weapon._is_crawl_limit_reached() is True

    def test_time_limit_stops_discovery_after_max_time(self, weapon_with_limits):
        """Test time limit stops discovery after max_time_seconds is reached."""
        weapon = weapon_with_limits(max_time_seconds=10)

        with patch('app.weapons.fullauto.time') as mock_time:
            # Start at 1000.0, then 1005.0 (5s elapsed - within limit), then 1011.0 (11s elapsed - over limit)
            mock_time.time.side_effect = [1000.0, 1000.0, 1005.0, 1011.0, 1011.0]

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.target('https://example.com')  # Sets start time to 1000.0

            # Add URL at 5 seconds elapsed (within limit)
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'
            )

            # Add URL at 11 seconds elapsed (over limit)
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page2'
            )

        # Should have first URL (from target) + page1, but not page2
        assert 'https://example.com/page1' in weapon._urls
        assert 'https://example.com/page2' not in weapon._urls
        assert weapon._is_crawl_limit_reached() is True

    def test_limits_checked_before_each_url_addition(self, weapon_with_limits):
        """Test that limits are checked before each URL addition."""
        weapon = weapon_with_limits(max_urls=3)

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.return_value = 1000.0

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.target('https://example.com')  # First URL

            # Add 2 more URLs successfully (total 3, at limit)
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'
            )
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page2'
            )

            # Attempt to add 4th URL
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page3'
            )

        assert 'https://example.com/page3' not in weapon._urls
        assert weapon._discovered_url_count == 3

    def test_existing_urls_continue_to_be_attacked_after_limit(self, weapon_with_limits):
        """Test that existing URLs continue to be attacked after crawl limit is reached."""
        weapon = weapon_with_limits(max_urls=2)

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.return_value = 1000.0

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                weapon.target('https://example.com')  # First URL

            # Add 2nd URL to reach limit
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'
            )

            # Mock successful HTTP response
            html_content = b'<html><body><a href="/newpage">Link</a></body></html>'
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = html_content
            mock_info = MagicMock()
            mock_info.get_content_type.return_value = 'text/html'
            mock_response.info.return_value = mock_info

            with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client

                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    # Call attack multiple times
                    result1 = weapon.attack()
                    result2 = weapon.attack()

            # Verify attacks continue successfully
            assert isinstance(result1, AttackResult)
            assert result1.num_hits == 1
            assert isinstance(result2, AttackResult)
            assert result2.num_hits == 1

            # Verify no new URLs discovered (list size remains 2)
            assert len(weapon._urls) == 2

            # Verify network client was called (attacks continue)
            assert mock_client.request.call_count == 2

    def test_configurable_limit_parameters(self, weapon_with_limits):
        """Test that limit parameters are configurable via constructor."""
        # Create weapon with custom limits
        weapon_custom = weapon_with_limits(max_urls=100, max_time_seconds=60)
        assert weapon_custom._max_urls == 100
        assert weapon_custom._max_time_seconds == 60

        # Create weapon with defaults
        weapon_default = FullAutoWeapon()
        assert weapon_default._max_urls == 500
        assert weapon_default._max_time_seconds == 180

    def test_combined_limits_url_count_hits_first(self, weapon_with_limits):
        """Test that crawl limit is reached when URL count limit hits first."""
        weapon = weapon_with_limits(max_urls=3, max_time_seconds=100)

        with patch('app.weapons.fullauto.time') as mock_time:
            # Minimal time elapsed
            mock_time.time.side_effect = [1000.0, 1000.1, 1000.2, 1000.3]

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                weapon.target('https://example.com')  # First URL at 1000.0

            # Add 2 more URLs to hit URL count limit
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'
            )
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page2'
            )

        assert weapon._discovered_url_count == 3
        assert weapon._is_crawl_limit_reached() is True  # URL limit hit first

    def test_combined_limits_time_hits_first(self, weapon_with_limits):
        """Test that crawl limit is reached when time limit hits first."""
        weapon = weapon_with_limits(max_urls=100, max_time_seconds=5)

        with patch('app.weapons.fullauto.time') as mock_time:
            # Start at 1000.0, add target and URLs within limit, then exceed 5 second limit
            mock_time.time.side_effect = [1000.0, 1001.0, 1002.0, 1003.0, 1006.0]

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                weapon.target('https://example.com')  # Start time at 1000.0

            # Add only 2 URLs
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'
            )
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page2'
            )

        assert weapon._discovered_url_count == 3  # target + 2 URLs
        assert weapon._is_crawl_limit_reached() is True  # Time limit hit first

    def test_start_time_set_on_first_target(self, weapon_with_limits):
        """Test that start time is set when first target is called."""
        weapon = weapon_with_limits()

        # Initially None
        assert weapon._start_time is None

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.return_value = 1000.0

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.target('https://example.com')

        assert weapon._start_time == 1000.0

    def test_discovered_url_count_increments_correctly(self, weapon_with_limits):
        """Test that discovered URL count increments correctly and ignores duplicates."""
        weapon = weapon_with_limits()

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.return_value = 1000.0

            # Initially 0
            assert weapon._discovered_url_count == 0

            with patch('app.net.url_ensure_valid', return_value='https://example.com'):
                weapon.target('https://example.com')  # Count = 1

            assert weapon._discovered_url_count == 1

            # Add 3 more unique URLs
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'
            )
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page2'
            )
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page3'
            )
            assert weapon._discovered_url_count == 4

            # Attempt to add duplicate URL
            weapon._add_url(
                parent_url='https://example.com/',
                new_url='https://example.com/page1'  # Duplicate
            )
            assert weapon._discovered_url_count == 4  # Duplicates not counted

    def test_attack_with_html_response_respects_url_limit(self, weapon_with_limits):
        """Test that attack() with HTML response respects URL limit during link discovery."""
        weapon = weapon_with_limits(max_urls=2)

        with patch('app.weapons.fullauto.time') as mock_time:
            mock_time.time.return_value = 1000.0

            with patch('app.net.url_ensure_valid', side_effect=lambda x: x):
                weapon.target('https://example.com')  # First URL

            # Mock NetworkClient to return HTML with 5 links
            html_content = b'''<html><body>
                <a href="/link1">Link 1</a>
                <a href="/link2">Link 2</a>
                <a href="/link3">Link 3</a>
                <a href="/link4">Link 4</a>
                <a href="/link5">Link 5</a>
            </body></html>'''

            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = html_content
            mock_info = MagicMock()
            mock_info.get_content_type.return_value = 'text/html'
            mock_response.info.return_value = mock_info

            with patch('app.weapons.fullauto.NetworkClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.request.return_value = (mock_response, 100, 200)
                mock_client_class.return_value = mock_client
                weapon._network_client = mock_client

                with patch('app.weapons.fullauto.random.randint', return_value=0):
                    # First attack discovers links
                    result1 = weapon.attack()

                    # Second attack should not discover more URLs
                    result2 = weapon.attack()

            # Should have original URL + 1 discovered (at limit)
            assert len(weapon._urls) == 2
            assert weapon._is_crawl_limit_reached() is True

            # Both attacks should succeed
            assert isinstance(result1, AttackResult)
            assert result1.num_hits == 1
            assert isinstance(result2, AttackResult)
            assert result2.num_hits == 1

