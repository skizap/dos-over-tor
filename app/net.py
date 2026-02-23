"""Network client module for making HTTP requests with user agent rotation.

This module provides a class-based interface for making HTTP requests with
configurable user agents and byte tracking capabilities.

The NetworkClient class offers instance-based state management, eliminating the need
for global variables while providing methods for request tracking and IP lookups.

Usage Examples:
    Basic usage with explicit method calls:
    >>> client = NetworkClient()
    >>> client.rotate_user_agent()
    >>> response, bytes_sent, bytes_received = client.request('GET', 'https://example.com')
    >>> print(f"Sent: {bytes_sent} bytes, Received: {bytes_received} bytes")

    Getting current user agent:
    >>> client = NetworkClient()
    >>> client.rotate_user_agent()
    >>> ua = client.get_user_agent()
    >>> print(f"Current User-Agent: {ua}")

    Looking up public IP:
    >>> client = NetworkClient()
    >>> ip = client.lookup_ip()
    >>> print(f"Public IP: {ip}")

Note:
    - The request() method returns a tuple of (response, bytes_sent, bytes_received)
    - Byte tracking provides best-effort estimates based on headers and content length
    - User agents are randomly generated for macOS and Windows platforms
"""

import random
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, Tuple

import user_agent


class RequestException(Exception):
    """Exception thrown when a call to request() fails.

    This exception is raised by NetworkClient methods when:
    - The request fails due to network errors
    - The user agent is not set before making a request
    - URL parsing or other request preparation fails

    Attributes:
        message: Explanation of the error that occurred.
    """

    pass


class NetworkClient:
    """Client for making HTTP requests with user agent rotation.

    This class provides methods to make HTTP requests with configurable user
    agents, track request/response bytes, and perform IP lookups.

    The client manages user agent state internally and provides best-effort
    byte tracking for monitoring network usage.

    Attributes:
        _user_agent: The current user agent string, or None if not set.
    """

    def __init__(self) -> None:
        """Initialize the NetworkClient with no user agent set."""
        self._user_agent: Optional[str] = None

    def rotate_user_agent(self) -> None:
        """Generate a new fake user agent for use with request().

        Creates a randomly generated user agent string for macOS or Windows
        platforms using the user_agent library.

        Example:
            >>> client = NetworkClient()
            >>> client.rotate_user_agent()
            >>> print(client.get_user_agent())
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...'
        """
        try:
            self._user_agent = user_agent.generate_user_agent(os=('mac', 'win'))
        except TypeError:
            # The user_agent library is broken in Python 3.12 due to randint(0, float)
            self._user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    def get_user_agent(self) -> Optional[str]:
        """Return the current user agent string.

        Returns the fake user agent which will be used with request(),
        or None if rotate_user_agent() has not been called.

        Returns:
            The current user agent string, or None if not set.

        Example:
            >>> client = NetworkClient()
            >>> client.rotate_user_agent()
            >>> ua = client.get_user_agent()
            >>> print(f"User-Agent: {ua}")
        """
        return self._user_agent

    def request(self, method: str, url: str) -> Tuple[Any, int, int]:
        """Make an HTTP request to the given URL with byte tracking.

        Sends an HTTP request with the configured user agent and returns
        the response along with best-effort estimates of bytes sent and received.

        Args:
            method: The HTTP method to use (e.g., 'GET', 'POST').
            url: The URL to request.

        Returns:
            A tuple containing:
            - The response object (or HTTPError exception on error status)
            - Estimated bytes sent for the request
            - Estimated bytes received for the response

        Raises:
            RequestException: If no user agent is set or if the request fails.

        Example:
            >>> client = NetworkClient()
            >>> client.rotate_user_agent()
            >>> response, sent, received = client.request('GET', 'https://example.com')
            >>> print(f"Request sent {sent} bytes, received {received} bytes")
        """
        if self._user_agent is None:
            raise RequestException("no user agent set; call rotate_user_agent() first")

        # Build headers with user agent
        headers = {
            'User-Agent': self._user_agent
        }

        # Calculate bytes sent estimate
        # Request line: METHOD URL HTTP/1.1\r\n
        bytes_sent = len(method) + len(url) + len(' HTTP/1.1\r\n')

        # Add headers size to bytes sent estimate
        for key, value in headers.items():
            bytes_sent += len(key) + len(': ') + len(value) + len('\r\n')

        # Add header/body separator
        bytes_sent += len('\r\n')

        # Body: 0 for GET requests (no body sent in this implementation)
        # Note: If POST/PUT with body is added later, include body length here

        response: Any = None
        bytes_received = 0

        try:
            request_obj = urllib.request.Request(
                url,
                method=method.upper(),
                headers=headers
            )

            response = urllib.request.urlopen(request_obj)

            # Calculate bytes received estimate
            # Response headers: estimate ~200 bytes (status line + common headers)
            bytes_received += 200

            # Response body: use Content-Length if available, or try non-consuming length hint
            content_length = response.headers.get('Content-Length')
            if content_length:
                bytes_received += int(content_length)
            else:
                # Use non-consuming hint if available; otherwise leave as headers-only estimate
                length_hint = getattr(response, 'length', None)
                if length_hint is not None:
                    bytes_received += length_hint

        except urllib.error.HTTPError as ex:
            # For HTTP errors, still estimate bytes received from error response
            response = ex
            bytes_received += 200  # Estimated response headers
            # Try to get Content-Length from error response if available
            content_length = ex.headers.get('Content-Length') if ex.headers else None
            if content_length:
                bytes_received += int(content_length)

        except Exception as ex:
            # Assume all other exceptions thrown are errors of some sort
            raise RequestException(str(ex))

        return response, bytes_sent, bytes_received

    def lookup_ip(self) -> str:
        """Query the public IP address via icanhazip.com.

        Polls a third-party service to determine the public-facing IP address.

        Returns:
            The public IP address as a string.

        Raises:
            RequestException: If the IP lookup request fails.

        Example:
            >>> client = NetworkClient()
            >>> ip = client.lookup_ip()
            >>> print(f"Public IP: {ip}")
        """
        try:
            response = urllib.request.urlopen('https://icanhazip.com')
            ip = response.read().decode('utf-8').strip('\n')
            return ip
        except Exception as ex:
            raise RequestException(f"failed to lookup IP; {str(ex)}")


def url_ensure_valid(url: str) -> str:
    """Ensure the given URL is valid and contains the correct scheme.

    Parses the URL and ensures it has a scheme (defaulting to https) and
    proper netloc formatting.

    Args:
        url: The URL to validate and fix.

    Returns:
        A properly formatted URL with scheme and netloc.

    Example:
        >>> url_ensure_valid('example.com/path')
        'https://example.com/path'
        >>> url_ensure_valid('http://example.com')
        'http://example.com'
    """
    scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)

    if not netloc:
        netloc, path = path, ''

    if not scheme:
        scheme = 'https'

    return urllib.parse.urlunparse(
        (scheme, netloc, path, params, query, fragment)
    )


def url_cache_buster(url: str) -> str:
    """Add a cache busting query string to the given URL.

    Appends a random query parameter to prevent caching of the request.

    Args:
        url: The URL to add the cache-busting parameter to.

    Returns:
        The URL with an added random query parameter.

    Example:
        >>> url_cache_buster('https://example.com/page')
        'https://example.com/page?123456789'
    """
    scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)

    # ensure that we pass integers to randint even if time is mocked as float
    query = "%d" % (
        int(random.randint(1, 999999999))
    )

    return urllib.parse.urlunparse(
        (scheme, netloc, path, params, query, fragment)
    )


# Module-level singleton instance for backward compatibility
_network_client: Optional[NetworkClient] = None


def new_user_agent() -> None:
    """Backward-compatible wrapper for NetworkClient.rotate_user_agent().

    Creates or reuses a module-level NetworkClient singleton and generates
    a new user agent.

    Example:
        >>> new_user_agent()
        >>> print(get_user_agent())
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...'
    """
    global _network_client

    if _network_client is None:
        _network_client = NetworkClient()

    _network_client.rotate_user_agent()


def get_user_agent() -> Optional[str]:
    """Backward-compatible wrapper for NetworkClient.get_user_agent().

    Returns the user agent from the module-level singleton.

    Returns:
        The current user agent string, or None if not set.

    Example:
        >>> new_user_agent()
        >>> ua = get_user_agent()
        >>> print(f"User-Agent: {ua}")
    """
    global _network_client

    if _network_client is None:
        _network_client = NetworkClient()

    return _network_client.get_user_agent()


def request(method: str, url: str) -> Any:
    """Backward-compatible wrapper for NetworkClient.request().

    Creates or reuses a module-level NetworkClient singleton and makes
    a request, returning only the response object for backward compatibility.

    Args:
        method: The HTTP method to use (e.g., 'GET', 'POST').
        url: The URL to request.

    Returns:
        The response object (or HTTPError exception on error status).

    Raises:
        RequestException: If the request fails or no user agent is set.

    Example:
        >>> new_user_agent()
        >>> response = request('GET', 'https://example.com')
        >>> print(response.status)
        200
    """
    global _network_client

    if _network_client is None:
        _network_client = NetworkClient()

    response, _, _ = _network_client.request(method, url)
    return response


def lookupip() -> str:
    """Backward-compatible wrapper for NetworkClient.lookup_ip().

    Queries the public IP address via the module-level singleton.

    Returns:
        The public IP address as a string.

    Raises:
        RequestException: If the IP lookup fails.

    Example:
        >>> ip = lookupip()
        >>> print(f"Public IP: {ip}")
    """
    global _network_client

    if _network_client is None:
        _network_client = NetworkClient()

    return _network_client.lookup_ip()
