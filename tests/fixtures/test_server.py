"""Reusable HTTP server fixtures for integration tests."""

from __future__ import annotations

import copy
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest


DEFAULT_FALLBACK_ROUTE = {
    "status_code": 200,
    "delay": 0,
    "body": b"<html><body>OK</body></html>",
}


DEFAULT_ROUTE_CONFIG = {
    "/": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Test Root</title></head>
<body>
<h1>Root Page</h1>
<a href="/page1">Page 1</a>
<a href="/page2">Page 2</a>
<a href="/page3">Page 3</a>
<a href="/page4">Page 4</a>
<a href="/page5">Page 5</a>
<a href="/page6">Page 6</a>
<a href="/page7">Page 7</a>
<a href="/page8">Page 8</a>
<a href="/page9">Page 9</a>
<a href="/page10">Page 10</a>
<a href="/page11">Page 11</a>
<a href="/page12">Page 12</a>
</body>
</html>""",
    },
    "/page1": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 1</title></head>
<body>
<h1>Page 1</h1>
<a href="/">Back to Root</a>
<a href="/page2">Page 2</a>
<a href="/page3">Page 3</a>
</body>
</html>""",
    },
    "/page2": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 2</title></head>
<body>
<h1>Page 2</h1>
<a href="/">Back to Root</a>
<a href="/page1">Page 1</a>
<a href="/page4">Page 4</a>
</body>
</html>""",
    },
    "/page3": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 3</title></head>
<body>
<h1>Page 3</h1>
<a href="/">Back to Root</a>
<a href="/page1">Page 1</a>
</body>
</html>""",
    },
    "/page4": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 4</title></head>
<body>
<h1>Page 4</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page5": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 5</title></head>
<body>
<h1>Page 5</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page6": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 6</title></head>
<body>
<h1>Page 6</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page7": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 7</title></head>
<body>
<h1>Page 7</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page8": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 8</title></head>
<body>
<h1>Page 8</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page9": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 9</title></head>
<body>
<h1>Page 9</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page10": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 10</title></head>
<body>
<h1>Page 10</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page11": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 11</title></head>
<body>
<h1>Page 11</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
    "/page12": {
        "status_code": 200,
        "delay": 0,
        "body": b"""<!DOCTYPE html>
<html>
<head><title>Page 12</title></head>
<body>
<h1>Page 12</h1>
<a href="/">Back to Root</a>
</body>
</html>""",
    },
}


class ConfigurableHTTPServer(ThreadingHTTPServer):
    """HTTP server with shared mutable state for request/connection tracking."""

    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]):
        super().__init__(server_address, handler_class)
        self.route_config: dict[str, dict[str, Any]] = {}
        self.request_log: list[dict[str, Any]] = []
        self.connection_log: list[socket.socket] = []
        self._log_lock = threading.Lock()


class TestHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves per-route configurable responses."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress handler logs to keep test output clean."""
        return

    def _resolve_route_config(self) -> dict[str, Any]:
        server = self.server
        if self.path in server.route_config:
            return server.route_config[self.path]
        if "default" in server.route_config:
            return server.route_config["default"]
        return DEFAULT_FALLBACK_ROUTE

    def _handle_request(self, method: str, include_body: bool = True) -> None:
        server = self.server
        cfg = self._resolve_route_config()

        delay = cfg.get("delay", 0)
        if delay > 0:
            time.sleep(delay)

        status_code = int(cfg.get("status_code", 200))
        body = cfg.get("body", DEFAULT_FALLBACK_ROUTE["body"])
        if isinstance(body, str):
            body = body.encode("utf-8")
        if body is None:
            body = b""

        self.send_response(status_code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if include_body:
            self.wfile.write(body)

        with server._log_lock:
            server.request_log.append(
                {
                    "path": self.path,
                    "method": method,
                    "timestamp": time.time(),
                }
            )

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_HEAD(self) -> None:
        self._handle_request("HEAD", include_body=False)


class SlowLorisTrackingHandler(TestHTTPHandler):
    """Handler variant that records accepted TCP connections in setup()."""

    def setup(self) -> None:
        super().setup()
        server = self.server
        with server._log_lock:
            server.connection_log.append(self.connection)


class TestServer:
    """Context manager for lifecycle management of configurable local HTTP servers."""

    def __init__(
        self,
        handler_class: type[BaseHTTPRequestHandler] = TestHTTPHandler,
        routes: dict[str, dict[str, Any]] | None = None,
    ):
        self._handler_class = handler_class
        self._routes = routes or {}
        self._server: ConfigurableHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._port: int | None = None

    def __enter__(self) -> "TestServer":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        server = ConfigurableHTTPServer(("127.0.0.1", port), self._handler_class)
        server.route_config = copy.deepcopy(self._routes)
        server.request_log = []
        server.connection_log = []
        server._log_lock = threading.Lock()

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        self._port = port
        self._server = server
        self._server_thread = server_thread
        return self

    def __exit__(self, *exc: object) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()

        if self._server_thread is not None:
            self._server_thread.join(timeout=1.0)

    @property
    def base_url(self) -> str:
        if self._port is None:
            raise RuntimeError("TestServer is not running")
        return f"http://127.0.0.1:{self._port}"

    @property
    def request_log(self) -> list[dict[str, Any]]:
        if self._server is None:
            raise RuntimeError("TestServer is not running")
        return self._server.request_log

    @property
    def connection_log(self) -> list[socket.socket]:
        if self._server is None:
            raise RuntimeError("TestServer is not running")
        return self._server.connection_log


@pytest.fixture(scope="function")
def test_server(request: pytest.FixtureRequest):
    routes = copy.deepcopy(getattr(request, "param", None) or DEFAULT_ROUTE_CONFIG)
    with TestServer(handler_class=TestHTTPHandler, routes=routes) as srv:
        yield srv


@pytest.fixture(scope="function")
def slowloris_test_server(request: pytest.FixtureRequest):
    routes = copy.deepcopy(getattr(request, "param", None) or DEFAULT_ROUTE_CONFIG)
    with TestServer(handler_class=SlowLorisTrackingHandler, routes=routes) as srv:
        yield srv

