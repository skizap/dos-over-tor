"""Tor client module for managing connections to the Tor network.

This module provides a class-based interface for connecting to and managing
Tor network connections, including identity rotation and SOCKS5 proxy configuration.

The TorClient class offers instance-based state management, eliminating the need
for global variables while providing scoped proxy configuration to prevent DNS leaks.

Usage Examples:
    Basic usage with explicit connect/close:
    >>> tor_client = TorClient()
    >>> tor_client.connect(address='127.0.0.1', proxy_port=9050, ctrl_port=9051)
    >>> tor_client.new_identity()
    >>> with tor_client.proxy_scope():
    ...     current_ip = tor_client.get_current_ip()
    ...     # All network operations here use Tor proxy
    >>> tor_client.close()

    Usage as context manager (automatic cleanup):
    >>> with TorClient() as client:
    ...     client.connect()
    ...     with client.proxy_scope():
    ...         ip = client.get_current_ip()

    The proxy_scope() context manager temporarily configures SOCKS5 proxy with
    remote DNS resolution (rdns=True) to prevent DNS leaks, then restores the
    original socket state on exit.

Note:
    - Requires a running Tor service with SOCKS proxy and control port enabled
    - The control port requires authentication (cookie or password)
    - Remote DNS is enabled by default to prevent DNS leaks
"""

import socket
import urllib.error
import urllib.request
from typing import Optional, Generator
from contextlib import contextmanager

import socks
import stem
import stem.control


class ConnectionErrorException(Exception):
    """Exception raised when a connection to Tor fails.

    This exception is raised by TorClient methods when:
    - Connection to the Tor control port fails
    - Connection to the Tor SOCKS proxy fails
    - Identity rotation fails due to lack of connection
    - IP lookup fails while proxy is active

    Attributes:
        message: Explanation of the error that occurred.
    """

    pass


class TorClient:
    """Client for managing Tor network connections.

    This class provides methods to connect to a Tor service, manage identity
    rotation, configure SOCKS5 proxy scoping, and perform IP lookups through
    the Tor network.

    The client supports usage as a context manager for automatic cleanup of
    the controller connection.

    Attributes:
        _controller: The stem controller instance for Tor control port access.
        _address: The address of the Tor service (default: 127.0.0.1).
        _proxy_port: The port for the Tor SOCKS proxy (default: 9050).
        _ctrl_port: The port for the Tor control port (default: 9051).
        _is_connected: Flag indicating whether the client is connected.
    """

    def __init__(self) -> None:
        """Initialize the TorClient with default values."""
        self._controller: Optional[stem.control.Controller] = None
        self._address: str = '127.0.0.1'
        self._proxy_port: int = 9050
        self._ctrl_port: int = 9051
        self._is_connected: bool = False

    def connect(
        self,
        address: str = '127.0.0.1',
        proxy_port: int = 9050,
        ctrl_port: int = 9051
    ) -> None:
        """Connect to the Tor service.

        Establishes a connection to the Tor controller via the control port
        and authenticates. Connection parameters are stored for later use by
        proxy_scope() and other methods.

        Args:
            address: The address of the Tor service (default: 127.0.0.1).
            proxy_port: The port for the Tor SOCKS proxy (default: 9050).
            ctrl_port: The port for the Tor control port (default: 9051).

        Raises:
            ConnectionErrorException: If connection to the control port fails.

        Example:
            >>> client = TorClient()
            >>> client.connect(address='127.0.0.1', proxy_port=9050, ctrl_port=9051)
        """
        self._address = address
        self._proxy_port = proxy_port
        self._ctrl_port = ctrl_port

        # Connect to controller
        try:
            self._controller = stem.control.Controller.from_port(
                address=address,
                port=ctrl_port
            )
            self._controller.authenticate()
            self._is_connected = True
        except Exception as ex:
            raise ConnectionErrorException(
                "failed to connect to control port; %s" % str(ex)
            )

    def new_identity(self) -> None:
        """Request a new identity from the Tor service.

        Sends a NEWNYM signal to the Tor controller to request a new circuit
        and IP address. This is useful for rotating identities during operation.

        DNS leak prevention is handled automatically by the proxy_scope()
        context manager which enables remote DNS resolution.

        Raises:
            ConnectionErrorException: If not connected to the Tor controller.

        Example:
            >>> client = TorClient()
            >>> client.connect()
            >>> client.new_identity()  # Get a new IP address
        """
        if self._controller is None:
            raise ConnectionErrorException(
                "cannot request new identity; not connected to Tor controller"
            )

        self._controller.signal(stem.Signal.NEWNYM)

    def get_current_ip(self) -> str:
        """Query the current public IP address through Tor.

        Fetches the public IP address by querying a third-party service
        (icanhazip.com) through the Tor network. This method should be called
        within a proxy_scope() context to ensure the request goes through Tor.

        Returns:
            The current public IP address as a string.

        Raises:
            ConnectionErrorException: If the IP lookup request fails.

        Example:
            >>> client = TorClient()
            >>> client.connect()
            >>> with client.proxy_scope():
            ...     ip = client.get_current_ip()
            ...     print(f"Current Tor IP: {ip}")
        """
        try:
            response = urllib.request.urlopen('https://icanhazip.com')
            ip = response.read().decode('utf-8').strip()
            return ip
        except Exception as ex:
            raise ConnectionErrorException(
                "failed to get current IP; %s" % str(ex)
            )

    @contextmanager
    def proxy_scope(self) -> Generator[None, None, None]:
        """Context manager for scoped SOCKS5 proxy configuration.

        Temporarily configures the global socket to use the Tor SOCKS5 proxy
        with remote DNS resolution enabled (rdns=True). This prevents DNS
        leaks by ensuring DNS queries go through the Tor network.

        On exit, the original socket class is restored regardless of whether
        an exception occurred.

        Yields:
            None: Control is yielded to the caller within the proxy scope.

        Raises:
            ConnectionErrorException: If proxy setup fails.

        Example:
            >>> client = TorClient()
            >>> client.connect()
            >>> with client.proxy_scope():
            ...     # All socket operations here use Tor proxy
            ...     response = urllib.request.urlopen('https://example.com')
            ...     # DNS queries also go through Tor (remote DNS)
            >>> # Outside the context, original socket behavior is restored
        """
        original_socket = socket.socket

        try:
            socks.setdefaultproxy(
                socks.PROXY_TYPE_SOCKS5,
                self._address,
                self._proxy_port,
                True  # rdns=True for remote DNS resolution (prevents DNS leaks)
            )
            socket.socket = socks.socksocket
            yield
        except Exception as ex:
            raise ConnectionErrorException(
                "failed to set up proxy; %s" % str(ex)
            )
        finally:
            socket.socket = original_socket

    def close(self) -> None:
        """Close the connection to the Tor controller.

        Closes the stem controller connection and resets the connection state.
        This method is safe to call multiple times.

        Example:
            >>> client = TorClient()
            >>> client.connect()
            >>> # ... use the client ...
            >>> client.close()
        """
        if self._controller is not None:
            self._controller.close()
            self._controller = None
            self._is_connected = False

    def __enter__(self) -> 'TorClient':
        """Enter the context manager protocol.

        Returns:
            The TorClient instance for use within the context.

        Example:
            >>> with TorClient() as client:
            ...     client.connect()
            ...     # Use the client
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager protocol.

        Automatically closes the controller connection when exiting the
        context, regardless of whether an exception occurred.

        Args:
            exc_type: The type of exception that occurred, or None.
            exc_val: The exception value, or None.
            exc_tb: The exception traceback, or None.
        """
        self.close()


# Module-level singleton instance for backward compatibility
_tor_client: Optional[TorClient] = None


def connect(**kwargs) -> None:
    """Backward-compatible wrapper for TorClient.connect().

    Creates or reuses a module-level TorClient singleton and connects it.

    Args:
        address: TOR service address (default = 127.0.0.1)
        proxy_port: TOR service proxy port (default = 9050)
        ctrl_port: TOR service control port (default = 9051)

    Raises:
        ConnectionErrorException: When connection to control port failed
    """
    global _tor_client

    if _tor_client is None:
        _tor_client = TorClient()

    address = kwargs.get('address', '127.0.0.1')
    proxy_port = kwargs.get('proxy_port', 9050)
    ctrl_port = kwargs.get('ctrl_port', 9051)

    _tor_client.connect(address=address, proxy_port=proxy_port, ctrl_port=ctrl_port)


def new_ident() -> None:
    """Backward-compatible wrapper for TorClient.new_identity().

    Requests a new identity from the Tor service via the singleton client.

    Raises:
        ConnectionErrorException: If not connected to the Tor controller.
    """
    global _tor_client

    if _tor_client is None:
        raise ConnectionErrorException("not connected; call connect() first")

    _tor_client.new_identity()


def close() -> None:
    """Backward-compatible wrapper for TorClient.close().

    Closes the connection to the Tor service via the singleton client.
    """
    global _tor_client

    if _tor_client is not None:
        _tor_client.close()
        _tor_client = None
