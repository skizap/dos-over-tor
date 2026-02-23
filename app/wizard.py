"""
Interactive wizard for guided attack configuration and execution.
"""

import urllib.parse
import click

from app.models import AttackConfig
from app.runner import AttackRunner

class InteractiveWizard:
    """
    Step-by-step CLI wizard that prompts the user for all attack parameters and delegates execution to `AttackRunner`.
    """

    def run(self) -> bool:
        """
        Run the interactive wizard.
        Steps:
        1. Mode selection
        2. Target URL
        3. Common options
        4. Identity rotation
        5. Mode-specific options
        :return: True if the attack ran successfully, False if aborted or failed
        """
        try:
            # Step 1: Mode selection
            click.echo("Select attack mode:")
            click.echo("  1 - singleshot")
            click.echo("  2 - fullauto")
            click.echo("  3 - slowloris")
            
            mode_choice = click.prompt("Mode", type=click.Choice(['1', '2', '3']))
            mode_map = {
                '1': 'singleshot',
                '2': 'fullauto',
                '3': 'slowloris'
            }
            mode = mode_map[mode_choice]
            
            # Step 2: Target URL
            while True:
                target = click.prompt("Target URL")
                parsed = urllib.parse.urlparse(target)
                if parsed.scheme in ('http', 'https') and parsed.netloc:
                    break
                click.echo("Invalid URL. Must include scheme (http/https) and domain.")
            
            # Step 3: Common options
            num_threads = click.prompt("Number of threads", type=click.IntRange(1, 100), default=10)
            http_method = click.prompt("HTTP method", type=click.Choice(['GET', 'POST', 'PUT', 'DELETE']), default='GET')
            cache_buster = click.confirm("Use cache buster?", default=False)
            tor_address = click.prompt("Tor address", default='127.0.0.1')
            tor_proxy_port = click.prompt("Tor proxy port", type=click.IntRange(1, 65535), default=9050)
            tor_ctrl_port = click.prompt("Tor control port", type=click.IntRange(1, 65535), default=9051)
            
            rotation_interval = click.prompt("Identity rotation interval (0 for none)", type=click.IntRange(0), default=0)
            identity_rotation_interval = None if rotation_interval == 0 else rotation_interval
            
            # Step 4: Mode-specific options
            slowloris_num_sockets = 100
            fullauto_max_urls = 500
            fullauto_max_time = 180
            
            if mode == 'slowloris':
                slowloris_num_sockets = click.prompt("Number of sockets", type=click.IntRange(1), default=100)
            elif mode == 'fullauto':
                fullauto_max_urls = click.prompt("Max URLs", type=click.IntRange(1), default=500)
                fullauto_max_time = click.prompt("Max time (seconds)", type=click.IntRange(1), default=180)
            
            # Step 5: Build config, run, return
            config = AttackConfig(
                mode=mode,
                target=target,
                num_threads=num_threads,
                http_method=http_method,
                cache_buster=cache_buster,
                tor_address=tor_address,
                tor_proxy_port=tor_proxy_port,
                tor_ctrl_port=tor_ctrl_port,
                identity_rotation_interval=identity_rotation_interval,
                slowloris_num_sockets=slowloris_num_sockets,
                fullauto_max_urls=fullauto_max_urls,
                fullauto_max_time=fullauto_max_time
            )
            
            runner = AttackRunner(config)
            return runner.run()
            
        except KeyboardInterrupt:
            click.echo("\nWizard aborted by user.")
            return False
