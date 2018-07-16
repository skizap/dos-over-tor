
import socket
import urllib.error
import socks
import stem
import stem.control


# stem controller for connecting to the TOR control port
_controller = None


class ConnectionErrorException(Exception):
    """
    Error exception thrown when failing to connect to remote
    """

    pass


def connect(**kwargs):
    """
    Attempt to make a connection to the TOR server. This will connect both to the proxy via the proxy port and
    the controller via the control port.

    :param address: TOR service address (default = 127.0.0.1)
    :param proxy_port: TOR service proxy port (default = 9050)
    :param ctrl_port: TOR service control port (default = 9051)
    :raises ConnectionErrorException: When connection to control port failed
    """

    global _controller

    address = kwargs['address'] if 'address' in kwargs else '127.0.0.1'
    proxy_port = kwargs['proxy_port'] if 'proxy_port' in kwargs else 9050
    ctrl_port = kwargs['ctrl_port'] if 'ctrl_port' in kwargs else 9051

    # connect to controller
    try:

        _controller = stem.control.Controller.from_port(
            address=address,
            port=ctrl_port
        )

        _controller.authenticate()

    except Exception as ex:

        raise ConnectionErrorException(
            "failed to connect to control port; %s" % str(ex)
        )

    # connect to proxy
    try:

        socks.setdefaultproxy(
            socks.PROXY_TYPE_SOCKS5,
            address,
            proxy_port,
            True
        )

        socket.socket = socks.socksocket

    except urllib.error.URLError as ex:

        raise ConnectionErrorException(
            "failed to connect to proxy; %s" % str(ex)
        )


def new_ident():
    """
    Request TOR server to aquire a new identity.
    """

    global _controller

    if _controller is not None:
        _controller.signal(stem.Signal.NEWNYM)


def close():
    """
    Close connection to the TOR server.
    """

    global _controller

    if _controller is not None:
        _controller.close()
