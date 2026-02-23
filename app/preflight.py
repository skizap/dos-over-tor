"""Pre-flight validation module for attack readiness checks.

This module provides the PreFlightValidator class for validating that all
prerequisites are met before starting an attack run. It checks Tor connectivity,
proxy functionality, and displays the attack configuration.

Usage Example:
    >>> from app.preflight import PreFlightValidator
    >>> from app.tor import TorClient
    >>> from app.models import AttackConfig
    >>> 
    >>> validator = PreFlightValidator()
    >>> tor_client = TorClient()
    >>> tor_client.connect()
    >>> config = AttackConfig(mode='singleshot', target='https://example.com')
    >>> 
    >>> if validator.validate(tor_client, config):
    ...     print("Ready to attack!")
    ... else:
    ...     print("Validation failed - check errors above")
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tor import TorClient, ConnectionErrorException
    from app.models import AttackConfig

import app.console


class PreFlightValidator:
    """Validates pre-attack prerequisites and displays configuration.
    
    This class performs comprehensive validation before an attack run:
    - Verifies Tor control connection is established
    - Tests Tor proxy connectivity and IP retrieval
    - Displays current Tor exit IP
    - Displays formatted attack configuration summary
    
    The validator uses the app.console module for consistent output formatting
    and follows the established codebase patterns for error handling and logging.
    
    Attributes:
        None - This is a stateless validator class.
    """
    
    def validate(self, tor_client: 'TorClient', config: 'AttackConfig') -> bool:
        """Validate all pre-attack prerequisites.
        
        Performs comprehensive validation checks:
        1. Verifies TorClient is connected to control port
        2. Tests proxy connectivity by retrieving current IP
        3. Displays configuration summary
        
        Args:
            tor_client: An instance of TorClient to validate connectivity.
            config: AttackConfig containing attack parameters to display.
            
        Returns:
            True if all validations pass, False if any check fails.
            
        Example:
            >>> validator = PreFlightValidator()
            >>> tor_client = TorClient()
            >>> tor_client.connect()
            >>> config = AttackConfig(mode='fullauto', target='https://target.com')
            >>> ready = validator.validate(tor_client, config)
            >>> if ready:
            ...     # Proceed with attack
        """
        try:
            # Check 1: Tor Control Connection
            if not tor_client._is_connected:
                app.console.error("Tor control connection failed - not connected to Tor")
                return False
            
            # Check 2 & 3: Tor Proxy Connectivity and Display Exit IP
            try:
                with tor_client.proxy_scope():
                    current_ip = tor_client.get_current_ip()
                    app.console.log(f"Current Tor exit IP: {current_ip}")
            except Exception as ex:
                # Check if it's a ConnectionErrorException
                if type(ex).__name__ == 'ConnectionErrorException':
                    app.console.error(f"Tor proxy connection failed - {str(ex)}")
                else:
                    app.console.error(f"Failed to retrieve Tor exit IP - {str(ex)}")
                return False
            
            # Check 4: Display Configuration Summary
            self._display_config_summary(config)
            
            return True
            
        except Exception as ex:
            app.console.error(f"Pre-flight validation failed unexpectedly - {str(ex)}")
            return False
    
    def _display_config_summary(self, config: 'AttackConfig') -> None:
        """Display formatted attack configuration summary.
        
        Outputs the attack configuration using app.console.system() with
        a clear, readable format. Handles mode-specific options and
        conditional display of optional settings.
        
        Args:
            config: AttackConfig containing the configuration to display.
            
        Example:
            >>> validator._display_config_summary(config)
            # Outputs:
            # Configuration:
            #   Mode: slowloris
            #   Target: https://example.com
            #   ...
        """
        app.console.system("Configuration:")
        app.console.system(f"  Mode: {config.mode}")
        app.console.system(f"  Target: {config.target}")
        app.console.system(f"  Threads: {config.num_threads}")
        app.console.system(f"  HTTP Method: {config.http_method}")
        app.console.system(f"  Cache Buster: {config.cache_buster}")
        
        # Identity rotation display
        if config.identity_rotation_interval is None:
            app.console.system("  Identity Rotation: Disabled")
        else:
            app.console.system(f"  Identity Rotation: {config.identity_rotation_interval} seconds")
        
        # Mode-specific options
        if config.mode == 'slowloris':
            app.console.system(f"  Sockets per Thread: {config.slowloris_num_sockets}")
        elif config.mode == 'fullauto':
            app.console.system(f"  Max URLs: {config.fullauto_max_urls}")
            app.console.system(f"  Max Time: {config.fullauto_max_time} seconds")
