# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Web — in-process HTTP-style API router."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from aura.utils import get_logger

_VERSION = "2.0.0"


class WebAPI:
    """
    In-process HTTP-style request router for remote control of AURa.

    No network listener is started — callers invoke :meth:`handle_request`
    directly (or via a thin transport shim).  This keeps the class fully
    testable with zero I/O.
    """

    def __init__(
        self,
        auth_enabled: bool = False,
        api_token: Optional[str] = None,
    ) -> None:
        self._routes: Dict[str, Callable] = {}
        self._auth_enabled = auth_enabled
        self._api_token = api_token
        self._log = get_logger("aura.web.api")
        self._log.debug(
            "WebAPI initialised (auth_enabled=%s).", auth_enabled
        )

    def register_route(self, path: str, handler: Callable) -> None:
        """Map *path* prefix to *handler*."""
        self._routes[path] = handler
        self._log.debug("Route registered: %s", path)

    def handle_request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        """
        Route an incoming request and return ``{status: int, body: dict}``.

        Built-in routes take precedence over registered routes.
        """
        headers = headers or {}
        body = body or {}

        if self._auth_enabled and not self._check_auth(headers):
            self._log.warning("Unauthorised request: %s %s", method, path)
            return {"status": 401, "body": {"error": "unauthorized"}}

        # Built-in routes
        if method == "GET" and path == "/health":
            return {"status": 200, "body": {"status": "ok", "version": _VERSION}}

        if method == "GET" and path == "/status":
            return {"status": 200, "body": {"running": True, "version": _VERSION}}

        if method == "POST" and path == "/command":
            command = body.get("command")
            if command and command in self._routes:
                try:
                    result = self._routes[command](body)
                    return {"status": 200, "body": result if isinstance(result, dict) else {"result": result}}
                except Exception as exc:
                    self._log.error("Command handler error (%s): %s", command, exc)
                    return {"status": 500, "body": {"error": str(exc)}}
            self._log.warning("Unknown command: %s", command)
            return {"status": 404, "body": {"error": "not found"}}

        # Registered path-prefix routes
        for registered_path, handler in self._routes.items():
            if path.startswith(registered_path):
                try:
                    result = handler({"method": method, "path": path, "body": body})
                    return {"status": 200, "body": result if isinstance(result, dict) else {"result": result}}
                except Exception as exc:
                    self._log.error("Route handler error (%s): %s", registered_path, exc)
                    return {"status": 500, "body": {"error": str(exc)}}

        self._log.debug("No route matched: %s %s", method, path)
        return {"status": 404, "body": {"error": "not found"}}

    def _check_auth(self, headers: dict) -> bool:
        """Return True if the request carries a valid Bearer token."""
        auth_header = headers.get("Authorization") or headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header[len("Bearer "):]
        return token == self._api_token
