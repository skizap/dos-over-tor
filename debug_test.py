from click.testing import CliRunner
from main import cli
from unittest.mock import patch
from app.tor import ConnectionErrorException
import traceback

def test_real_tor_connection_failure():
    runner = CliRunner()
    with patch('app.runner.TorClient.connect') as mock_connect:
        mock_connect.side_effect = ConnectionErrorException("Connection failed")
        try:
            result = runner.invoke(cli, ['singleshot', 'https://example.com'], catch_exceptions=True)
            print(f"Exit code: {result.exit_code}")
            print(f"Exception: {repr(result.exception)}")
            if result.exception:
                traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
        except Exception as e:
            print(f"Caught exception: {e}")
            traceback.print_exc()

test_real_tor_connection_failure()
