"""Integration tests for CLI-to-AttackRunner pipeline."""

import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from main import cli
from app.models import AttackConfig, AttackSummary
from app.tor import ConnectionErrorException


@pytest.fixture
def cli_runner():
    """Return a Click CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_runner_success():
    """Patch AttackRunner with successful run() returning True."""
    with patch('main.AttackRunner') as mock_class:
        mock_instance = MagicMock()
        mock_instance.run.return_value = True
        mock_class.return_value = mock_instance
        yield mock_class, mock_instance


@pytest.fixture
def mock_runner_failure():
    """Patch AttackRunner with failed run() returning False."""
    with patch('main.AttackRunner') as mock_class:
        mock_instance = MagicMock()
        mock_instance.run.return_value = False
        mock_class.return_value = mock_instance
        yield mock_class, mock_instance


@pytest.fixture
def mock_attack_runner_real():
    """Patch AttackRunner to return a real instance with mocked dependencies."""
    from app.tor import TorClient
    from app.net import NetworkClient
    from app.preflight import PreFlightValidator
    from app.reporter import SummaryReporter
    from app.runner import AttackRunner
    
    with patch('main.AttackRunner') as mock_class, \
         patch('app.runner.Platoon') as mock_platoon_class, \
         patch('app.console._ttysize', return_value=(80, 24)):
        
        # We want to capture the constructed runners
        created_runners = []
        
        def side_effect(config):
            tor_client = MagicMock(spec=TorClient)
            tor_client.proxy_scope.return_value.__enter__.return_value = None
            tor_client.proxy_scope.return_value.__exit__.return_value = None
            
            network_client = MagicMock(spec=NetworkClient)
            network_client.get_user_agent.return_value = "Mocked User Agent"
            
            preflight_validator = MagicMock(spec=PreFlightValidator)
            preflight_validator.validate.return_value = True
            
            summary_reporter = MagicMock(spec=SummaryReporter)
            
            runner = AttackRunner(
                config=config,
                tor_client=tor_client,
                network_client=network_client,
                preflight_validator=preflight_validator,
                summary_reporter=summary_reporter
            )
            
            # Save the mocked dependencies on the runner instance for assertion later
            runner._mock_tor_client = tor_client
            runner._mock_network_client = network_client
            runner._mock_preflight_validator = preflight_validator
            runner._mock_summary_reporter = summary_reporter
            
            # Mock monitor summary so reporter doesn't crash
            mock_platoon_instance = mock_platoon_class.return_value
            mock_platoon_instance._monitor.get_summary.return_value = MagicMock()
            
            created_runners.append(runner)
            return runner
            
        mock_class.side_effect = side_effect
        yield mock_class, created_runners


class TestTorConnectivityIntegration:
    """Integration tests for Tor connectivity via CLI."""

    def test_singleshot_full_pipeline(self, cli_runner, mock_attack_runner_real):
        """Test singleshot command executes the full pipeline with mocked dependencies."""
        mock_class, created_runners = mock_attack_runner_real
        
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--tor-address', '192.168.1.1',
            '--tor-proxy-port', '9050',
            '--tor-ctrl-port', '9051'
        ])
        
        assert result.exit_code == 0
        assert len(created_runners) == 1
        runner = created_runners[0]
        
        # Verify TorClient interactions
        runner._mock_tor_client.connect.assert_called_once_with(
            address='192.168.1.1',
            proxy_port=9050,
            ctrl_port=9051
        )
        runner._mock_tor_client.proxy_scope.assert_called_once()
        
        # Verify PreFlightValidator interactions
        runner._mock_preflight_validator.validate.assert_called_once_with(
            runner._mock_tor_client, runner._config
        )
        
        # Verify NetworkClient interactions
        runner._mock_network_client.rotate_user_agent.assert_called_once()
        runner._mock_network_client.get_user_agent.assert_called_once()
        
        # Verify SummaryReporter interactions
        runner._mock_summary_reporter.display.assert_called_once()

    def test_fullauto_full_pipeline(self, cli_runner, mock_attack_runner_real):
        """Test fullauto command executes the full pipeline with mocked dependencies."""
        mock_class, created_runners = mock_attack_runner_real
        
        result = cli_runner.invoke(cli, [
            'fullauto', 'https://example.com'
        ])
        
        assert result.exit_code == 0
        assert len(created_runners) == 1
        runner = created_runners[0]
        
        runner._mock_tor_client.connect.assert_called_once()
        runner._mock_preflight_validator.validate.assert_called_once()
        runner._mock_network_client.rotate_user_agent.assert_called_once()
        runner._mock_summary_reporter.display.assert_called_once()

    def test_slowloris_full_pipeline(self, cli_runner, mock_attack_runner_real):
        """Test slowloris command executes the full pipeline with mocked dependencies."""
        mock_class, created_runners = mock_attack_runner_real
        
        result = cli_runner.invoke(cli, [
            'slowloris', 'https://example.com'
        ])
        
        assert result.exit_code == 0
        assert len(created_runners) == 1
        runner = created_runners[0]
        
        runner._mock_tor_client.connect.assert_called_once()
        runner._mock_preflight_validator.validate.assert_called_once()
        runner._mock_network_client.rotate_user_agent.assert_called_once()
        runner._mock_summary_reporter.display.assert_called_once()
class TestSingleShotCommand:
    """Tests for the singleshot CLI command."""

    def test_singleshot_minimal_args(self, cli_runner, mock_runner_success):
        """Test singleshot with minimal arguments exits with code 0."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
        
        assert result.exit_code == 0
        mock_class.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_singleshot_builds_correct_attack_config(self, cli_runner, mock_runner_success):
        """Test singleshot builds correct AttackConfig."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
        
        assert result.exit_code == 0
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'singleshot'
        assert config.target == 'https://example.com'

    def test_singleshot_with_all_options(self, cli_runner, mock_runner_success):
        """Test singleshot with all CLI options."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--tor-address', '127.0.0.1',
            '--tor-proxy-port', '9050',
            '--tor-ctrl-port', '9051',
            '--num-threads', '10',
            '--http-method', 'POST',
            '--cache-buster',
            '--identity-rotation-interval', '60'
        ])
        
        assert result.exit_code == 0
        config = mock_class.call_args[0][0]
        assert config.tor_address == '127.0.0.1'
        assert config.tor_proxy_port == 9050
        assert config.tor_ctrl_port == 9051
        assert config.num_threads == 10
        assert config.http_method == 'POST'
        assert config.cache_buster is True
        assert config.identity_rotation_interval == 60

    def test_singleshot_runner_failure_exits_1(self, cli_runner, mock_runner_failure):
        """Test singleshot runner failure exits with code 1."""
        result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
        assert result.exit_code == 1


class TestFullAutoCommand:
    """Tests for the fullauto CLI command."""

    def test_fullauto_minimal_args(self, cli_runner, mock_runner_success):
        """Test fullauto with minimal arguments exits with code 0."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, ['fullauto', 'https://example.com'])
        
        assert result.exit_code == 0
        mock_class.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_fullauto_builds_correct_attack_config(self, cli_runner, mock_runner_success):
        """Test fullauto builds correct AttackConfig with defaults."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, ['fullauto', 'https://example.com'])
        
        assert result.exit_code == 0
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'fullauto'
        assert config.fullauto_max_urls == 500
        assert config.fullauto_max_time == 180

    def test_fullauto_with_max_urls_and_max_time(self, cli_runner, mock_runner_success):
        """Test fullauto with --max-urls and --max-time options."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, [
            'fullauto', 'https://example.com',
            '--max-urls', '100',
            '--max-time', '90'
        ])
        
        assert result.exit_code == 0
        config = mock_class.call_args[0][0]
        assert config.fullauto_max_urls == 100
        assert config.fullauto_max_time == 90

    def test_fullauto_runner_failure_exits_1(self, cli_runner, mock_runner_failure):
        """Test fullauto runner failure exits with code 1."""
        result = cli_runner.invoke(cli, ['fullauto', 'https://example.com'])
        assert result.exit_code == 1


class TestSlowLorisCommand:
    """Tests for the slowloris CLI command."""

    def test_slowloris_minimal_args(self, cli_runner, mock_runner_success):
        """Test slowloris with minimal arguments exits with code 0."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, ['slowloris', 'https://example.com'])
        
        assert result.exit_code == 0
        mock_class.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_slowloris_builds_correct_attack_config(self, cli_runner, mock_runner_success):
        """Test slowloris builds correct AttackConfig with defaults."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, ['slowloris', 'https://example.com'])
        
        assert result.exit_code == 0
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'slowloris'
        assert config.slowloris_num_sockets == 100

    def test_slowloris_with_num_sockets(self, cli_runner, mock_runner_success):
        """Test slowloris with --num-sockets option."""
        mock_class, mock_instance = mock_runner_success
        result = cli_runner.invoke(cli, [
            'slowloris', 'https://example.com',
            '--num-sockets', '200'
        ])
        
        assert result.exit_code == 0
        config = mock_class.call_args[0][0]
        assert config.slowloris_num_sockets == 200

    def test_slowloris_runner_failure_exits_1(self, cli_runner, mock_runner_failure):
        """Test slowloris runner failure exits with code 1."""
        result = cli_runner.invoke(cli, ['slowloris', 'https://example.com'])
        assert result.exit_code == 1


class TestPreFlightValidationFlow:
    """Tests for pre-flight validation flow."""

    def test_preflight_success_exits_0(self, cli_runner):
        """Test preflight success exits with code 0."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.return_value = True
            mock_class.return_value = mock_instance
            
            result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            assert result.exit_code == 0

    def test_preflight_failure_exits_1(self, cli_runner):
        """Test preflight failure exits with code 1."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.return_value = False
            mock_class.return_value = mock_instance
            
            result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            assert result.exit_code == 1

    def test_tor_connection_failure_exits_1(self, cli_runner):
        """Test Tor connection failure exits with code 1."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.return_value = False
            mock_class.return_value = mock_instance
            
            result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            assert result.exit_code == 1

    @patch('app.console._ttysize')
    def test_real_tor_connection_failure_exits_1(self, mock_ttysize, cli_runner):
        """Test real AttackRunner handling Tor connection failure."""
        mock_ttysize.return_value = (80, 24)
        with patch('app.runner.TorClient.connect') as mock_connect:
            mock_connect.side_effect = ConnectionErrorException("Connection failed")
            
            result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            
            assert result.exit_code == 1
            assert result.exception is None or isinstance(result.exception, SystemExit)
            assert 'Failed to connect to Tor' in result.output


class TestSignalHandling:
    """Tests for signal handling."""

    def test_keyboard_interrupt_exits_1(self, cli_runner):
        """Test KeyboardInterrupt exits with code 1."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.side_effect = KeyboardInterrupt()
            mock_class.return_value = mock_instance
            
            result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            assert result.exit_code == 1

    def test_keyboard_interrupt_does_not_call_exit_0(self, cli_runner):
        """Test KeyboardInterrupt does not exit with code 0."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.side_effect = KeyboardInterrupt()
            mock_class.return_value = mock_instance
            
            result = cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            assert result.exit_code != 0


class TestInteractiveCommand:
    """Integration tests for the interactive CLI command."""

    # Input string layout (newline-separated, \n = accept default):
    #   Line 1:  mode choice ('1' / '2' / '3')
    #   Line 2:  target URL
    #   Line 3:  num_threads  (or \n for default)
    #   Line 4:  http_method  (or \n for default)
    #   Line 5:  cache_buster confirm ('n' / 'y')
    #   Line 6:  tor_address  (or \n for default)
    #   Line 7:  tor_proxy_port (or \n for default)
    #   Line 8:  tor_ctrl_port  (or \n for default)
    #   Line 9:  identity_rotation_interval
    #   Line 10+ mode-specific (slowloris: num_sockets; fullauto: max_urls, max_time)

    def test_interactive_singleshot_exits_0_on_success(self, cli_runner, mock_runner_success):
        """Test interactive singleshot with success exits code 0."""
        mock_class, mock_instance = mock_runner_success
        # singleshot input: mode=1, url, defaults for rest, rotation=0
        input_data = "1\nhttps://example.com\n\n\nn\n\n\n\n0\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 0

    def test_interactive_singleshot_exits_1_on_failure(self, cli_runner, mock_runner_failure):
        """Test interactive singleshot with failure exits code 1."""
        mock_class, mock_instance = mock_runner_failure
        input_data = "1\nhttps://example.com\n\n\nn\n\n\n\n0\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 1

    def test_interactive_builds_correct_singleshot_config(self, cli_runner, mock_runner_success):
        """Test interactive builds correct singleshot AttackConfig with all fields."""
        mock_class, mock_instance = mock_runner_success
        # Input: mode=1, url, defaults for num_threads/http_method, cache_buster=n,
        # defaults for tor_address/tor_proxy_port/tor_ctrl_port, rotation=0
        input_data = "1\nhttps://example.com\n\n\nn\n\n\n\n0\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 0
        
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'singleshot'
        assert config.target == 'https://example.com'
        assert config.num_threads == 10  # default
        assert config.http_method == 'GET'  # default
        assert config.cache_buster is False  # 'n' in input
        assert config.tor_address == '127.0.0.1'  # default
        assert config.tor_proxy_port == 9050  # default
        assert config.tor_ctrl_port == 9051  # default

    def test_interactive_slowloris_prompts_num_sockets(self, cli_runner, mock_runner_success):
        """Test interactive slowloris prompts for num_sockets with all config fields."""
        mock_class, mock_instance = mock_runner_success
        # slowloris: mode=3, url, num_threads=20, http_method=POST, cache_buster=y,
        # tor_address=192.168.1.1, tor_proxy_port=8080, tor_ctrl_port=8081,
        # rotation=0, num_sockets=200
        input_data = "3\nhttps://example.com\n20\nPOST\ny\n192.168.1.1\n8080\n8081\n0\n200\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 0
        
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'slowloris'
        assert config.target == 'https://example.com'
        assert config.num_threads == 20
        assert config.http_method == 'POST'
        assert config.cache_buster is True
        assert config.tor_address == '192.168.1.1'
        assert config.tor_proxy_port == 8080
        assert config.tor_ctrl_port == 8081
        assert config.identity_rotation_interval is None
        assert config.slowloris_num_sockets == 200

    def test_interactive_fullauto_prompts_max_urls_and_max_time(self, cli_runner, mock_runner_success):
        """Test interactive fullauto prompts for max_urls and max_time with all config fields."""
        mock_class, mock_instance = mock_runner_success
        # fullauto: mode=2, url, num_threads=25, http_method=PUT, cache_buster=y,
        # tor_address=10.0.0.1, tor_proxy_port=9150, tor_ctrl_port=9151,
        # rotation=0, max_urls=100, max_time=90
        input_data = "2\nhttps://example.com\n25\nPUT\ny\n10.0.0.1\n9150\n9151\n0\n100\n90\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 0
        
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'fullauto'
        assert config.target == 'https://example.com'
        assert config.num_threads == 25
        assert config.http_method == 'PUT'
        assert config.cache_buster is True
        assert config.tor_address == '10.0.0.1'
        assert config.tor_proxy_port == 9150
        assert config.tor_ctrl_port == 9151
        assert config.identity_rotation_interval is None
        assert config.fullauto_max_urls == 100
        assert config.fullauto_max_time == 90

    def test_interactive_identity_rotation_interval_zero_is_none(self, cli_runner, mock_runner_success):
        """Test interactive with rotation=0 results in None with all config fields."""
        mock_class, mock_instance = mock_runner_success
        # Use non-default values to verify all fields are captured correctly
        input_data = "1\nhttps://example.com\n15\nDELETE\ny\n192.168.1.1\n9052\n9053\n0\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 0
        
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'singleshot'
        assert config.target == 'https://example.com'
        assert config.num_threads == 15
        assert config.http_method == 'DELETE'
        assert config.cache_buster is True
        assert config.tor_address == '192.168.1.1'
        assert config.tor_proxy_port == 9052
        assert config.tor_ctrl_port == 9053
        assert config.identity_rotation_interval is None

    def test_interactive_identity_rotation_interval_nonzero(self, cli_runner, mock_runner_success):
        """Test interactive with rotation=60 passes through with all config fields."""
        mock_class, mock_instance = mock_runner_success
        # Use non-default values to verify all fields are captured correctly
        input_data = "1\nhttps://example.com\n30\nPOST\nn\n10.0.0.1\n9150\n9151\n60\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        assert result.exit_code == 0
        
        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'singleshot'
        assert config.target == 'https://example.com'
        assert config.num_threads == 30
        assert config.http_method == 'POST'
        assert config.cache_buster is False
        assert config.tor_address == '10.0.0.1'
        assert config.tor_proxy_port == 9150
        assert config.tor_ctrl_port == 9151
        assert config.identity_rotation_interval == 60

    def test_interactive_keyboard_interrupt_exits_1(self, cli_runner):
        """Test KeyboardInterrupt in interactive wizard exits code 1."""
        with patch('main.InteractiveWizard') as mock_wizard_class:
            mock_wizard = MagicMock()
            mock_wizard.run.side_effect = KeyboardInterrupt()
            mock_wizard_class.return_value = mock_wizard
            
            result = cli_runner.invoke(cli, ['interactive'])
            assert result.exit_code == 1

    def test_interactive_invalid_url_reprompts(self, cli_runner, mock_runner_success):
        """Test invalid URL in input causes re-prompt and recovery."""
        mock_class, mock_instance = mock_runner_success
        # First URL is invalid, second is valid - wizard should recover
        input_data = "1\nnot-a-url\nhttps://example.com\n\n\nn\n\n\n\n0\n"
        
        result = cli_runner.invoke(cli, ['interactive'], input=input_data)
        # Should exit 0 because wizard recovered and completed
        assert result.exit_code == 0


class TestSummaryReportFlow:
    """Tests for summary report flow."""

    def test_attack_runner_run_called_on_success(self, cli_runner):
        """Test AttackRunner.run() is called on success."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.return_value = True
            mock_class.return_value = mock_instance
            
            cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            mock_instance.run.assert_called_once()

    def test_attack_runner_constructed_with_attack_config_instance(self, cli_runner):
        """Test AttackRunner is constructed with AttackConfig instance."""
        with patch('main.AttackRunner') as mock_class:
            mock_instance = MagicMock()
            mock_instance.run.return_value = True
            mock_class.return_value = mock_instance
            
            cli_runner.invoke(cli, ['singleshot', 'https://example.com'])
            config = mock_class.call_args[0][0]
            assert isinstance(config, AttackConfig)


class TestErrorHandling:
    """Tests for CLI error handling (Click validation errors)."""

    def test_invalid_http_method_shows_error(self, cli_runner):
        """Test invalid HTTP method shows Click error."""
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--http-method', 'PATCH'
        ])
        assert result.exit_code == 2
        assert 'Invalid value' in result.output

    def test_invalid_proxy_port_out_of_range(self, cli_runner):
        """Test invalid proxy port shows Click error."""
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--tor-proxy-port', '99999'
        ])
        assert result.exit_code == 2

    def test_invalid_ctrl_port_out_of_range(self, cli_runner):
        """Test invalid control port shows Click error."""
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--tor-ctrl-port', '0'
        ])
        assert result.exit_code == 2

    def test_missing_target_shows_error(self, cli_runner):
        """Test missing target argument shows Click error."""
        result = cli_runner.invoke(cli, ['singleshot'])
        assert result.exit_code == 2
        assert 'Missing argument' in result.output

    def test_invalid_num_threads_zero(self, cli_runner):
        """Test invalid num_threads (zero) shows Click error."""
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--num-threads', '0'
        ])
        assert result.exit_code == 2

    def test_invalid_identity_rotation_interval_zero(self, cli_runner):
        """Test invalid identity_rotation_interval (zero) shows Click error."""
        result = cli_runner.invoke(cli, [
            'singleshot', 'https://example.com',
            '--identity-rotation-interval', '0'
        ])
        assert result.exit_code == 2
