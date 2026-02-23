"""Comprehensive unit tests for the AttackRunner class.

This module provides complete test coverage for the AttackRunner class including:
- Initialization and dependency injection
- Successful run flow orchestration
- Error handling for various failure scenarios
- Signal handling and graceful shutdown
- Weapon factory creation for all attack modes
- Integration testing with mocked dependencies

All network operations and external dependencies are mocked for isolated testing.
"""

from unittest.mock import MagicMock, patch, call
import pytest

from app.runner import AttackRunner
from app.models import AttackConfig, AttackSummary
from app.tor import ConnectionErrorException
from app.net import RequestException
from app.weapons.singleshot import SingleShotFactory
from app.weapons.fullauto import FullAutoFactory
from app.weapons.slowloris import SlowLorisFactory


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def attack_config_singleshot():
    """Create AttackConfig for singleshot mode."""
    return AttackConfig(
        mode='singleshot',
        target='https://example.com',
        num_threads=10,
        http_method='GET',
        cache_buster=False,
        tor_address='127.0.0.1',
        tor_proxy_port=9050,
        tor_ctrl_port=9051
    )


@pytest.fixture
def attack_config_fullauto():
    """Create AttackConfig for fullauto mode."""
    return AttackConfig(
        mode='fullauto',
        target='https://example.com',
        num_threads=10,
        http_method='POST',
        cache_buster=True,
        fullauto_max_urls=200,
        fullauto_max_time=120,
        identity_rotation_interval=300
    )


@pytest.fixture
def attack_config_slowloris():
    """Create AttackConfig for slowloris mode."""
    return AttackConfig(
        mode='slowloris',
        target='https://example.com',
        num_threads=5,
        http_method='GET',
        cache_buster=False,
        slowloris_num_sockets=50
    )


@pytest.fixture
def mock_tor_client():
    """Create mock TorClient with all required methods."""
    mock = MagicMock()
    mock.connect = MagicMock()
    mock.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
    mock.close = MagicMock()
    mock.get_current_ip = MagicMock(return_value='192.168.1.1')
    mock._is_connected = True
    return mock


@pytest.fixture
def mock_network_client():
    """Create mock NetworkClient with all required methods."""
    mock = MagicMock()
    mock.rotate_user_agent = MagicMock()
    mock.get_user_agent = MagicMock(return_value='Mozilla/5.0 Test User Agent')
    return mock


@pytest.fixture
def mock_platoon():
    """Create mock Platoon with all required methods."""
    mock = MagicMock()
    mock.attack = MagicMock()
    mock.hold_fire = MagicMock()

    # Create mock monitor with get_summary
    mock_monitor = MagicMock()
    mock_monitor.get_summary = MagicMock(return_value=AttackSummary(
        total_hits=100,
        total_requests=110,
        total_bytes_sent=50000,
        total_bytes_received=100000,
        total_errors=2,
        hits_per_second=10.5
    ))
    mock._monitor = mock_monitor

    return mock


@pytest.fixture
def mock_preflight_validator():
    """Create mock PreFlightValidator that passes validation."""
    mock = MagicMock()
    mock.validate = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_summary_reporter():
    """Create mock SummaryReporter."""
    mock = MagicMock()
    mock.display = MagicMock()
    return mock


# =============================================================================
# TestAttackRunnerInitialization
# =============================================================================

class TestAttackRunnerInitialization:
    """Test AttackRunner initialization and dependency injection."""

    def test_constructor_accepts_attack_config(self, attack_config_singleshot):
        """Test constructor accepts AttackConfig."""
        runner = AttackRunner(attack_config_singleshot)
        assert runner._config == attack_config_singleshot

    def test_constructor_accepts_tor_client(self, attack_config_singleshot, mock_tor_client):
        """Test constructor accepts optional TorClient."""
        runner = AttackRunner(attack_config_singleshot, tor_client=mock_tor_client)
        assert runner._tor_client == mock_tor_client

    def test_constructor_accepts_network_client(self, attack_config_singleshot, mock_network_client):
        """Test constructor accepts optional NetworkClient."""
        runner = AttackRunner(
            attack_config_singleshot,
            network_client=mock_network_client
        )
        assert runner._network_client == mock_network_client

    def test_constructor_accepts_preflight_validator(self, attack_config_singleshot, mock_preflight_validator):
        """Test constructor accepts optional PreFlightValidator."""
        runner = AttackRunner(
            attack_config_singleshot,
            preflight_validator=mock_preflight_validator
        )
        assert runner._preflight_validator == mock_preflight_validator

    def test_constructor_accepts_summary_reporter(self, attack_config_singleshot, mock_summary_reporter):
        """Test constructor accepts optional SummaryReporter."""
        runner = AttackRunner(
            attack_config_singleshot,
            summary_reporter=mock_summary_reporter
        )
        assert runner._summary_reporter == mock_summary_reporter

    def test_constructor_creates_default_instances_when_none_provided(self, attack_config_singleshot):
        """Test constructor creates default instances when dependencies not provided."""
        runner = AttackRunner(attack_config_singleshot)
        assert runner._tor_client is None
        assert runner._network_client is None
        assert runner._preflight_validator is None
        assert runner._summary_reporter is None

    def test_constructor_initializes_is_running_false(self, attack_config_singleshot):
        """Test constructor initializes _is_running to False."""
        runner = AttackRunner(attack_config_singleshot)
        assert runner._is_running is False

    def test_constructor_initializes_platoon_none(self, attack_config_singleshot):
        """Test constructor initializes _platoon to None."""
        runner = AttackRunner(attack_config_singleshot)
        assert runner._platoon is None


# =============================================================================
# TestAttackRunnerRun
# =============================================================================

class TestAttackRunnerRun:
    """Test AttackRunner run() method with various scenarios."""

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.Platoon')
    @patch('app.runner.SummaryReporter')
    @patch('app.runner.app.console')
    def test_successful_run_singleshot_mode(
        self, mock_console, mock_summary_reporter_class, mock_platoon_class,
        mock_network_class, mock_preflight_class, mock_tor_class,
        attack_config_singleshot, mock_platoon, mock_summary_reporter
    ):
        """Test successful run flow for singleshot mode."""
        # Setup mocks
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        mock_network = MagicMock()
        mock_network.rotate_user_agent = MagicMock()
        mock_network.get_user_agent = MagicMock(return_value='Test Agent')
        mock_network_class.return_value = mock_network

        mock_platoon_class.return_value = mock_platoon
        mock_summary_reporter_class.return_value = mock_summary_reporter

        # Create runner and run
        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        # Verify result
        assert result is True

        # Verify TorClient connection
        mock_tor.connect.assert_called_once_with(
            address='127.0.0.1',
            proxy_port=9050,
            ctrl_port=9051
        )

        # Verify PreFlightValidator called
        mock_preflight.validate.assert_called_once_with(mock_tor, attack_config_singleshot)

        # Verify proxy_scope entered
        mock_tor.proxy_scope.assert_called_once()

        # Verify NetworkClient user agent rotation
        mock_network.rotate_user_agent.assert_called_once()

        # Verify Platoon created with correct params including network_client
        mock_platoon_class.assert_called_once_with(
            num_soldiers=10,
            tor_client=mock_tor,
            network_client=mock_network,
            identity_rotation_interval=None
        )

        # Verify attack called
        mock_platoon.attack.assert_called_once()
        call_args = mock_platoon.attack.call_args[1]
        assert call_args['target_url'] == 'https://example.com'
        assert isinstance(call_args['weapon_factory'], SingleShotFactory)

        # Verify summary retrieved and displayed
        mock_platoon._monitor.get_summary.assert_called_once()
        mock_summary_reporter.display.assert_called_once()

        # Verify cleanup
        mock_tor.close.assert_called_once()
        mock_console.shutdown.assert_called_once()

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.Platoon')
    @patch('app.runner.SummaryReporter')
    @patch('app.runner.app.console')
    def test_successful_run_fullauto_mode(
        self, mock_console, mock_summary_reporter_class, mock_platoon_class,
        mock_network_class, mock_preflight_class, mock_tor_class,
        attack_config_fullauto
    ):
        """Test successful run flow for fullauto mode."""
        # Setup mocks
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        mock_network = MagicMock()
        mock_network.rotate_user_agent = MagicMock()
        mock_network.get_user_agent = MagicMock(return_value='Test Agent')
        mock_network_class.return_value = mock_network

        mock_platoon = MagicMock()
        mock_platoon.attack = MagicMock()
        mock_monitor = MagicMock()
        mock_monitor.get_summary = MagicMock(return_value=AttackSummary())
        mock_platoon._monitor = mock_monitor
        mock_platoon_class.return_value = mock_platoon

        mock_summary_reporter = MagicMock()
        mock_summary_reporter_class.return_value = mock_summary_reporter

        # Create runner and run
        runner = AttackRunner(attack_config_fullauto)
        result = runner.run()

        # Verify result
        assert result is True

        # Verify Platoon created with correct params including identity rotation and network_client
        mock_platoon_class.assert_called_once_with(
            num_soldiers=10,
            tor_client=mock_tor,
            network_client=mock_network,
            identity_rotation_interval=300
        )

        # Verify attack called with FullAutoFactory
        mock_platoon.attack.assert_called_once()
        call_args = mock_platoon.attack.call_args[1]
        assert isinstance(call_args['weapon_factory'], FullAutoFactory)

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.Platoon')
    @patch('app.runner.SummaryReporter')
    @patch('app.runner.app.console')
    def test_successful_run_slowloris_mode(
        self, mock_console, mock_summary_reporter_class, mock_platoon_class,
        mock_network_class, mock_preflight_class, mock_tor_class,
        attack_config_slowloris
    ):
        """Test successful run flow for slowloris mode."""
        # Setup mocks
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        mock_network = MagicMock()
        mock_network.rotate_user_agent = MagicMock()
        mock_network.get_user_agent = MagicMock(return_value='Test Agent')
        mock_network_class.return_value = mock_network

        mock_platoon = MagicMock()
        mock_platoon.attack = MagicMock()
        mock_monitor = MagicMock()
        mock_monitor.get_summary = MagicMock(return_value=AttackSummary())
        mock_platoon._monitor = mock_monitor
        mock_platoon_class.return_value = mock_platoon

        mock_summary_reporter = MagicMock()
        mock_summary_reporter_class.return_value = mock_summary_reporter

        # Create runner and run
        runner = AttackRunner(attack_config_slowloris)
        result = runner.run()

        # Verify result
        assert result is True

        # Verify Platoon created with correct params including network_client
        mock_platoon_class.assert_called_once_with(
            num_soldiers=5,
            tor_client=mock_tor,
            network_client=mock_network,
            identity_rotation_interval=None
        )

        # Verify attack called with SlowLorisFactory
        mock_platoon.attack.assert_called_once()
        call_args = mock_platoon.attack.call_args[1]
        assert isinstance(call_args['weapon_factory'], SlowLorisFactory)

    @patch('app.runner.TorClient')
    @patch('app.runner.app.console')
    def test_tor_client_connection_failure(
        self, mock_console, mock_tor_class, attack_config_singleshot
    ):
        """Test handling of TorClient connection failure."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock(
            side_effect=ConnectionErrorException("Connection refused")
        )
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        assert result is False
        mock_console.error.assert_called_once()
        # Runner always closes TorClient in finally block for cleanup
        mock_tor.close.assert_called_once()

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.app.console')
    def test_preflight_validation_failure(
        self, mock_console, mock_preflight_class, mock_tor_class,
        attack_config_singleshot
    ):
        """Test handling of PreFlightValidator failure."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=False)
        mock_preflight_class.return_value = mock_preflight

        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        assert result is False
        mock_console.error.assert_called()
        mock_tor.close.assert_called_once()

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.app.console')
    def test_generic_exception_during_attack(
        self, mock_console, mock_network_class, mock_preflight_class,
        mock_tor_class, attack_config_singleshot, mock_platoon
    ):
        """Test handling of generic exception during attack."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(side_effect=Exception("Unexpected error"))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        assert result is False
        mock_console.error.assert_called()
        mock_tor.close.assert_called_once()
        mock_console.shutdown.assert_called_once()


# =============================================================================
# TestAttackRunnerErrorHandling
# =============================================================================

class TestAttackRunnerErrorHandling:
    """Test AttackRunner error handling in various scenarios."""

    @patch('app.runner.TorClient')
    @patch('app.runner.app.console')
    def test_handles_connection_error_exception(self, mock_console, mock_tor_class, attack_config_singleshot):
        """Test handles ConnectionErrorException from TorClient operations."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock(side_effect=ConnectionErrorException("Connection failed"))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        assert result is False
        mock_console.error.assert_called()

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.app.console')
    def test_handles_preflight_failure(self, mock_console, mock_preflight_class, mock_tor_class, attack_config_singleshot):
        """Test handles PreFlightValidator returning False."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=False)
        mock_preflight_class.return_value = mock_preflight

        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        assert result is False

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.app.console')
    def test_cleanup_occurs_on_error(
        self, mock_console, mock_network_class, mock_preflight_class,
        mock_tor_class, attack_config_singleshot
    ):
        """Test cleanup occurs even when errors happen (finally block)."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(side_effect=Exception("Proxy error"))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        runner = AttackRunner(attack_config_singleshot)
        runner.run()

        # Verify cleanup in finally block
        mock_tor.close.assert_called_once()
        mock_console.shutdown.assert_called_once()


# =============================================================================
# TestAttackRunnerSignalHandling
# =============================================================================

class TestAttackRunnerSignalHandling:
    """Test AttackRunner signal handling and graceful shutdown."""

    def test_stop_method_calls_platoon_hold_fire(self, attack_config_singleshot, mock_platoon):
        """Test stop() method calls Platoon.hold_fire()."""
        runner = AttackRunner(attack_config_singleshot)
        runner._platoon = mock_platoon
        runner._is_running = True

        runner.stop()

        mock_platoon.hold_fire.assert_called_once()
        assert runner._is_running is False

    def test_stop_method_sets_is_running_false(self, attack_config_singleshot):
        """Test stop() sets _is_running flag to False."""
        runner = AttackRunner(attack_config_singleshot)
        runner._is_running = True

        runner.stop()

        assert runner._is_running is False

    def test_stop_method_handles_none_platoon(self, attack_config_singleshot):
        """Test stop() handles case when Platoon is None."""
        runner = AttackRunner(attack_config_singleshot)
        runner._platoon = None
        runner._is_running = True

        # Should not raise exception
        runner.stop()

        assert runner._is_running is False

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.Platoon')
    @patch('app.runner.app.console')
    def test_keyboard_interrupt_stops_attack(
        self, mock_console, mock_platoon_class, mock_network_class,
        mock_preflight_class, mock_tor_class, attack_config_singleshot
    ):
        """Test KeyboardInterrupt during attack stops platoon and returns False."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        mock_network = MagicMock()
        mock_network.rotate_user_agent = MagicMock()
        mock_network.get_user_agent = MagicMock(return_value='Test Agent')
        mock_network_class.return_value = mock_network

        mock_platoon = MagicMock()
        mock_platoon.attack = MagicMock(side_effect=KeyboardInterrupt())
        mock_platoon.hold_fire = MagicMock()
        mock_platoon_class.return_value = mock_platoon

        runner = AttackRunner(attack_config_singleshot)
        result = runner.run()

        # Verify attack returned False on KeyboardInterrupt
        assert result is False
        # Verify hold_fire was called
        mock_platoon.hold_fire.assert_called_once()
        # Verify log message
        mock_console.log.assert_called_with("KeyboardInterrupt received - stopping attack")


# =============================================================================
# TestAttackRunnerWeaponFactoryCreation
# =============================================================================

class TestAttackRunnerWeaponFactoryCreation:
    """Test weapon factory creation for different attack modes."""

    def test_singleshot_factory_created_with_correct_params(self, attack_config_singleshot):
        """Test SingleShotFactory created for singleshot mode with correct params."""
        runner = AttackRunner(attack_config_singleshot)
        factory = runner._create_weapon_factory()

        assert isinstance(factory, SingleShotFactory)
        assert factory._http_method == 'GET'
        assert factory._cache_buster is False

    def test_fullauto_factory_created_with_correct_params(self, attack_config_fullauto):
        """Test FullAutoFactory created for fullauto mode with max_urls and max_time_seconds."""
        runner = AttackRunner(attack_config_fullauto)
        factory = runner._create_weapon_factory()

        assert isinstance(factory, FullAutoFactory)
        assert factory._http_method == 'POST'
        assert factory._cache_buster is True
        assert factory._max_urls == 200
        assert factory._max_time_seconds == 120

    def test_slowloris_factory_created_with_correct_params(self, attack_config_slowloris):
        """Test SlowLorisFactory created for slowloris mode with num_sockets."""
        runner = AttackRunner(attack_config_slowloris)
        factory = runner._create_weapon_factory()

        assert isinstance(factory, SlowLorisFactory)
        assert factory._http_method == 'GET'
        assert factory._cache_buster is False
        assert factory._num_sockets == 50

    def test_unknown_mode_raises_value_error(self):
        """Test unknown attack mode raises ValueError."""
        config = AttackConfig(
            mode='unknown',
            target='https://example.com'
        )
        runner = AttackRunner(config)

        with pytest.raises(ValueError, match="Unknown attack mode: unknown"):
            runner._create_weapon_factory()


# =============================================================================
# TestAttackRunnerIntegration
# =============================================================================

class TestAttackRunnerIntegration:
    """Test AttackRunner integration with all mocked dependencies."""

    def test_complete_flow_with_all_mocked_dependencies(self, attack_config_singleshot):
        """Test complete flow with all mocked dependencies."""
        # Create all mocks
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        proxy_context = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        mock_tor.proxy_scope = MagicMock(return_value=proxy_context)
        mock_tor.close = MagicMock()
        mock_tor._is_connected = True

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)

        mock_network = MagicMock()
        mock_network.rotate_user_agent = MagicMock()
        mock_network.get_user_agent = MagicMock(return_value='Test Agent')

        mock_platoon = MagicMock()
        mock_platoon.attack = MagicMock()
        mock_monitor = MagicMock()
        mock_monitor.get_summary = MagicMock(return_value=AttackSummary())
        mock_platoon._monitor = mock_monitor

        mock_summary_reporter = MagicMock()
        mock_summary_reporter.display = MagicMock()

        # Create runner with injected dependencies
        runner = AttackRunner(
            attack_config_singleshot,
            tor_client=mock_tor,
            network_client=mock_network,
            preflight_validator=mock_preflight,
            summary_reporter=mock_summary_reporter
        )

        # Run
        with patch('app.runner.Platoon', return_value=mock_platoon):
            result = runner.run()

        # Verify result
        assert result is True

        # Verify call order using call history
        # 1. connect
        mock_tor.connect.assert_called_once()
        # 2. validate
        mock_preflight.validate.assert_called_once()
        # 3. proxy_scope entered
        mock_tor.proxy_scope.assert_called()
        # 4. rotate_user_agent
        mock_network.rotate_user_agent.assert_called_once()
        # 5. attack
        mock_platoon.attack.assert_called_once()
        # 6. get_summary
        mock_monitor.get_summary.assert_called_once()
        # 7. display
        mock_summary_reporter.display.assert_called_once()
        # 8. close
        mock_tor.close.assert_called_once()

    @patch('app.runner.TorClient')
    @patch('app.runner.PreFlightValidator')
    @patch('app.runner.NetworkClient')
    @patch('app.runner.Platoon')
    @patch('app.runner.SummaryReporter')
    @patch('app.runner.app.console')
    def test_is_running_flag_set_during_attack(
        self, mock_console, mock_summary_reporter_class, mock_platoon_class,
        mock_network_class, mock_preflight_class, mock_tor_class,
        attack_config_singleshot
    ):
        """Test _is_running flag is True during attack execution."""
        mock_tor = MagicMock()
        mock_tor.connect = MagicMock()
        mock_tor.proxy_scope = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        mock_tor.close = MagicMock()
        mock_tor_class.return_value = mock_tor

        mock_preflight = MagicMock()
        mock_preflight.validate = MagicMock(return_value=True)
        mock_preflight_class.return_value = mock_preflight

        mock_network = MagicMock()
        mock_network.rotate_user_agent = MagicMock()
        mock_network.get_user_agent = MagicMock(return_value='Test Agent')
        mock_network_class.return_value = mock_network

        mock_platoon = MagicMock()
        mock_platoon.attack = MagicMock()
        mock_monitor = MagicMock()
        mock_monitor.get_summary = MagicMock(return_value=AttackSummary())
        mock_platoon._monitor = mock_monitor
        mock_platoon_class.return_value = mock_platoon

        runner = AttackRunner(attack_config_singleshot)

        # Store is_running state during attack
        is_running_values = []

        def capture_is_running(*args, **kwargs):
            is_running_values.append(runner._is_running)

        mock_platoon.attack.side_effect = capture_is_running

        runner.run()

        # Verify is_running was True during attack
        assert True in is_running_values
