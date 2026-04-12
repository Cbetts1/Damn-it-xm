# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Remote — HTTP control server and request handler."""

from __future__ import annotations

import http.server
import json
import threading
from typing import Optional

from aura.utils import get_logger
from aura.web.api import WebAPI

_logger = get_logger("aura.remote.server")


class RemoteRequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Minimal ``BaseHTTPRequestHandler`` that delegates all requests to the
    :class:`WebAPI` instance held on the server.

    Supported methods: GET, POST, OPTIONS.
    All responses include permissive CORS headers.
    """

    # Injected by RemoteControlServer after construction
    web_api: WebAPI
    _request_counter_lock: threading.Lock
    _request_counter: list  # mutable container so subclass can mutate

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_cors(200, {})

    def do_GET(self) -> None:  # noqa: N802
        result = self.web_api.handle_request(
            "GET", self.path, {}, self._headers_dict()
        )
        self._send_json(result["status"], result["body"])
        self._increment_counter()

    def do_POST(self) -> None:  # noqa: N802
        body: dict = {}
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, ValueError) as exc:
                _logger.warning("RemoteRequestHandler: bad JSON body: %s", exc)
                body = {}

        result = self.web_api.handle_request(
            "POST", self.path, body, self._headers_dict()
        )
        self._send_json(result["status"], result["body"])
        self._increment_counter()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers_dict(self) -> dict:
        return {k: v for k, v in self.headers.items()}

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _send_cors(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self._add_cors_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _add_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization",
        )

    def _increment_counter(self) -> None:
        with self._request_counter_lock:
            self._request_counter[0] += 1

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
        _logger.debug("RemoteRequestHandler: " + fmt, *args)


class RemoteControlServer:
    """
    Thin HTTP server that exposes the :class:`WebAPI` over TCP.

    Uses only the stdlib ``http.server.HTTPServer`` — no external deps.
    Port 8765 is chosen because it is >1024 and safe to bind without root
    (required on Termux/Android).
    """

    def __init__(
        self,
        web_api: WebAPI,
        host: str = "0.0.0.0",
        port: int = 8765,
        auth_token: Optional[str] = None,
    ) -> None:
        self._web_api = web_api
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._lock = threading.RLock()
        self._running: bool = False
        self._server: Optional[http.server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._request_count: list = [0]  # mutable so handler can update
        self._counter_lock = threading.Lock()
        _logger.info("RemoteControlServer: host=%s  port=%d", host, port)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the HTTP server in a background daemon thread (idempotent)."""
        with self._lock:
            if self._running:
                return

            web_api = self._web_api
            request_count = self._request_count
            counter_lock = self._counter_lock

            class _Handler(RemoteRequestHandler):
                pass

            _Handler.web_api = web_api  # type: ignore[attr-defined]
            _Handler._request_counter = request_count  # type: ignore[attr-defined]
            _Handler._request_counter_lock = counter_lock  # type: ignore[attr-defined]

            self._server = http.server.HTTPServer((self._host, self._port), _Handler)
            self._running = True

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="aura-remote-server",
            daemon=True,
        )
        self._thread.start()
        _logger.info("RemoteControlServer: listening on %s", self.address)

    def stop(self) -> None:
        """Shut down the HTTP server."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._server is not None:
                self._server.shutdown()
                self._server = None
        _logger.info("RemoteControlServer: stopped")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def address(self) -> str:
        return f"{self._host}:{self._port}"

    def metrics(self) -> dict:
        with self._counter_lock:
            handled = self._request_count[0]
        with self._lock:
            running = self._running
        return {
            "host": self._host,
            "port": self._port,
            "is_running": running,
            "requests_handled": handled,
        }
