#!env python3

import app.console
import app.net
import app.tor
import fire


class BFDCLI:

    def __init__(
            self,
            tor_address='127.0.0.1',
            tor_proxy_port=9050,
            tor_ctrl_port=9051,
            max_threads=10
        ):
        """

        :param max_threads: Maximum of threads to spin up for the attack
        """

        self._tor_address = tor_address
        self._tor_proxy_port = tor_proxy_port
        self._tor_ctrl_port = tor_ctrl_port

    def singleshot(self, target):
        """
        Run an attack on a single URL.
        :param target: The target URL of the attack
        """

        try:

            self._connect()

            app.console.system("running singleshot")
            # app.aresenal.singleshot.run(
            #     target=target
            # )

        except Exception as ex:

            app.console.error(str(ex))

        self._shutdown()


    def _connect(self):
        """
        Connect to the TOR server
        """

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
        app.console.system("identity on TOR; %s" % ourip)

    def _shutdown(self):
        """
        Shutdown
        """

        app.console.system("shutting down")

        app.console.system("closing connection to TOR")
        app.tor.close()

        app.console.shutdown()


if __name__ == '__main__':
    fire.Fire(BFDCLI)
