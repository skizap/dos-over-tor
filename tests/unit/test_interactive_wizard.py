"""Unit tests for the InteractiveWizard class."""

import pytest
from unittest.mock import patch, MagicMock, call

from app.wizard import InteractiveWizard
from app.models import AttackConfig


# Fixtures ----------------------------------------------------------------

@pytest.fixture
def wizard_prompt_defaults():
    """Return default side_effect values for a complete singleshot run."""
    return ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]


@pytest.fixture
def mock_runner():
    """Patch AttackRunner and yield (mock_class, mock_instance)."""
    with patch('app.wizard.AttackRunner') as mock_class:
        mock_instance = MagicMock()
        mock_instance.run.return_value = True
        mock_class.return_value = mock_instance
        yield mock_class, mock_instance


# Test Classes ------------------------------------------------------------

class TestModeMapping:
    """Tests that mode selection maps to correct AttackConfig.mode values."""

    def test_mode_1_selects_singleshot(self, mock_runner):
        """Test mode '1' sets config.mode to 'singleshot'."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        config = mock_class.call_args[0][0]
        assert config.mode == 'singleshot'

    def test_mode_2_selects_fullauto(self, mock_runner):
        """Test mode '2' sets config.mode to 'fullauto'."""
        mock_class, _ = mock_runner
        side_effect = ['2', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0, 500, 180]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        config = mock_class.call_args[0][0]
        assert config.mode == 'fullauto'

    def test_mode_3_selects_slowloris(self, mock_runner):
        """Test mode '3' sets config.mode to 'slowloris'."""
        mock_class, _ = mock_runner
        side_effect = ['3', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0, 100]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        config = mock_class.call_args[0][0]
        assert config.mode == 'slowloris'


class TestURLValidation:
    """Tests for URL validation and re-prompting behavior."""

    def test_valid_http_url_accepted(self, mock_runner):
        """Test valid http:// URL is accepted without re-prompting."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'http://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        # Count URL prompts
        url_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Target URL"]
        assert len(url_calls) == 1

    def test_valid_https_url_accepted(self, mock_runner):
        """Test valid https:// URL is accepted without re-prompting."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        url_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Target URL"]
        assert len(url_calls) == 1

    def test_invalid_url_no_scheme_reprompts(self, mock_runner):
        """Test URL without scheme triggers re-prompt."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'not-a-url', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        url_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Target URL"]
        assert len(url_calls) == 2

    def test_invalid_url_ftp_scheme_reprompts(self, mock_runner):
        """Test URL with ftp:// scheme triggers re-prompt."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'ftp://example.com', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        url_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Target URL"]
        assert len(url_calls) == 2

    def test_invalid_url_no_netloc_reprompts(self, mock_runner):
        """Test URL without netloc triggers re-prompt."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        url_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Target URL"]
        assert len(url_calls) == 2


class TestModeSpecificPrompts:
    """Tests for mode-specific prompt behavior."""

    def test_slowloris_prompts_num_sockets(self, mock_runner):
        """Test slowloris mode prompts for 'Number of sockets'."""
        mock_class, _ = mock_runner
        side_effect = ['3', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0, 100]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        socket_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Number of sockets"]
        assert len(socket_calls) == 1

    def test_singleshot_does_not_prompt_num_sockets(self, mock_runner):
        """Test singleshot mode does not prompt for 'Number of sockets'."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        socket_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Number of sockets"]
        assert len(socket_calls) == 0

    def test_fullauto_prompts_max_urls_and_max_time(self, mock_runner):
        """Test fullauto mode prompts for 'Max URLs' and 'Max time'."""
        mock_class, _ = mock_runner
        side_effect = ['2', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0, 500, 180]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        max_urls_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Max URLs"]
        max_time_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Max time (seconds)"]
        assert len(max_urls_calls) == 1
        assert len(max_time_calls) == 1

    def test_singleshot_does_not_prompt_fullauto_options(self, mock_runner):
        """Test singleshot mode does not prompt for fullauto options."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect) as mock_prompt:
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        max_urls_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Max URLs"]
        max_time_calls = [c for c in mock_prompt.call_args_list if c[0][0] == "Max time (seconds)"]
        assert len(max_urls_calls) == 0
        assert len(max_time_calls) == 0


class TestAttackConfigConstruction:
    """Tests that AttackConfig is correctly constructed from prompt inputs."""

    def test_config_fields_match_prompt_inputs(self, mock_runner):
        """Test all AttackConfig fields match the values fed via side_effect."""
        mock_class, _ = mock_runner
        # Non-default values for unambiguous assertions
        side_effect = [
            '1',                    # mode choice
            'https://example.com',  # target
            25,                     # num_threads
            'POST',                 # http_method
            '192.168.1.1',          # tor_address
            8080,                   # tor_proxy_port
            8081,                   # tor_ctrl_port
            60                      # rotation_interval
        ]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=True):  # cache_buster = True
                wizard = InteractiveWizard()
                wizard.run()

        config = mock_class.call_args[0][0]
        assert isinstance(config, AttackConfig)
        assert config.mode == 'singleshot'
        assert config.target == 'https://example.com'
        assert config.num_threads == 25
        assert config.http_method == 'POST'
        assert config.cache_buster is True
        assert config.tor_address == '192.168.1.1'
        assert config.tor_proxy_port == 8080
        assert config.tor_ctrl_port == 8081
        assert config.identity_rotation_interval == 60

    def test_identity_rotation_interval_zero_becomes_none(self, mock_runner):
        """Test rotation interval of 0 becomes None in config."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        config = mock_class.call_args[0][0]
        assert config.identity_rotation_interval is None

    def test_identity_rotation_interval_nonzero_passed_through(self, mock_runner):
        """Test non-zero rotation interval is passed through to config."""
        mock_class, _ = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 60]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        config = mock_class.call_args[0][0]
        assert config.identity_rotation_interval == 60

    def test_attack_runner_run_is_called(self, mock_runner):
        """Test AttackRunner.run() is called exactly once."""
        mock_class, mock_instance = mock_runner
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                wizard.run()

        mock_instance.run.assert_called_once()

    def test_run_returns_true_on_success(self, mock_runner):
        """Test wizard returns True when runner.run() returns True."""
        mock_class, mock_instance = mock_runner
        mock_instance.run.return_value = True
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                result = wizard.run()

        assert result is True

    def test_run_returns_false_on_failure(self, mock_runner):
        """Test wizard returns False when runner.run() returns False."""
        mock_class, mock_instance = mock_runner
        mock_instance.run.return_value = False
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                result = wizard.run()

        assert result is False


class TestKeyboardInterrupt:
    """Tests for KeyboardInterrupt handling."""

    def test_keyboard_interrupt_in_prompt_returns_false(self, mock_runner):
        """Test KeyboardInterrupt during prompt returns False without raising."""
        with patch('app.wizard.click.prompt', side_effect=KeyboardInterrupt()):
            wizard = InteractiveWizard()
            result = wizard.run()

        assert result is False

    def test_keyboard_interrupt_in_runner_returns_false(self, mock_runner):
        """Test KeyboardInterrupt during runner.run() returns False."""
        mock_class, mock_instance = mock_runner
        mock_instance.run.side_effect = KeyboardInterrupt()
        side_effect = ['1', 'https://example.com', 10, 'GET', '127.0.0.1', 9050, 9051, 0]

        with patch('app.wizard.click.prompt', side_effect=side_effect):
            with patch('app.wizard.click.confirm', return_value=False):
                wizard = InteractiveWizard()
                result = wizard.run()

        assert result is False
