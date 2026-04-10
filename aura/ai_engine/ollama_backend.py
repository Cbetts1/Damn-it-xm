# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Ollama Backend
===================
Connects AURa to a locally-running `Ollama <https://ollama.com>`_ server.

Ollama runs as an independent OS-level process (a proper server daemon), so
model weights **never load into the phone/device Python process** — they live
inside the Ollama server memory, which the Virtual Cloud layer manages and
routes to.

Default model: ``llama3.1:8b`` — the largest capable open-source model that
runs on commodity hardware without a dedicated GPU.

Users can override via the ``AURA_OLLAMA_MODEL`` env var or
``AURaConfig.ollama.model``.

Graceful degradation
--------------------
If the Ollama server is not running, ``is_ready()`` returns ``False`` and
``generate()`` returns a stub response — the rest of AURa continues normally.

To start the server run::

    ollama serve                    # starts the Ollama daemon
    ollama pull llama3.1:8b         # download the model once (~4.7 GB)

or let AURa do it automatically via the ``cloud-ai pull`` shell command.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Generator, Optional

from aura.config import OllamaConfig
from aura.ai_engine.engine import AIResponse, BaseBackend
from aura.utils import get_logger

_logger = get_logger("aura.ai_engine.ollama")

# Model used when none is configured.  llama3.1:8b is the largest model that
# comfortably runs on CPU-only hardware; bump to llama3.1:70b when a GPU node
# is available.
DEFAULT_MODEL = "llama3.1:8b"

# How long (seconds) to wait for an Ollama /api/tags health probe.
_HEALTH_TIMEOUT = 3


class OllamaBackend(BaseBackend):
    """
    Ollama-powered inference backend.

    All HTTP calls go to the Ollama REST API; no model weights are loaded
    into the AURa process, keeping device RAM free.  The Virtual Cloud CPU
    routes tasks here as background workers.
    """

    def __init__(self, config: OllamaConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")
        self._model = config.model if config.model else DEFAULT_MODEL
        self._timeout = config.timeout_seconds
        _logger.debug(
            "OllamaBackend created (url=%s, model=%s).",
            self._base_url,
            self._model,
        )

    # ------------------------------------------------------------------
    # Backend interface
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return True when the Ollama server is reachable and has the model."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_HEALTH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            # Ollama names are like "llama3.1:8b" — check prefix match
            model_base = self._model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> AIResponse:
        """Send *prompt* to the Ollama server and return the response."""
        start = time.monotonic()

        if not self._server_up():
            _logger.warning("OllamaBackend.generate: server not reachable — stub.")
            return AIResponse(
                text=(
                    "Ollama server not running.  Start it with: ollama serve\n"
                    f"Then pull the model: ollama pull {self._model}"
                ),
                model=f"ollama-stub:{self._model}",
                tokens_used=0,
                latency_ms=0.0,
            )

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self._base_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode())

            text = data.get("response", "")
            tokens_used = (
                data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
            )
            latency_ms = (time.monotonic() - start) * 1000.0
            _logger.debug(
                "OllamaBackend generated %d token(s) in %.0f ms.",
                tokens_used,
                latency_ms,
            )
            return AIResponse(
                text=text,
                model=self._model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                metadata={
                    "total_duration_ns": data.get("total_duration"),
                    "done": data.get("done", True),
                },
            )

        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace") if hasattr(exc, "read") else ""
            _logger.error("OllamaBackend HTTP %s: %s", exc.code, body_text)
            return AIResponse(
                text=f"Ollama error {exc.code}: {body_text}",
                model=self._model,
                tokens_used=0,
                latency_ms=(time.monotonic() - start) * 1000.0,
            )
        except Exception as exc:
            _logger.error("OllamaBackend.generate error: %s", exc)
            return AIResponse(
                text=f"Ollama backend error: {exc}",
                model=self._model,
                tokens_used=0,
                latency_ms=(time.monotonic() - start) * 1000.0,
            )

    def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream tokens from Ollama line by line."""
        if not self._server_up():
            yield (
                "Ollama server not running.  "
                f"Start it with: ollama serve && ollama pull {self._model}"
            )
            return

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self._base_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line.decode())
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            _logger.error("OllamaBackend.stream error: %s", exc)
            yield f"[stream error: {exc}]"

    # ------------------------------------------------------------------
    # Ollama-specific helpers (model management)
    # ------------------------------------------------------------------

    def list_models(self) -> list:
        """Return the list of locally available Ollama models."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_HEALTH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            return data.get("models", [])
        except Exception:
            return []

    def pull_model(self, model: Optional[str] = None) -> bool:
        """
        Ask the Ollama server to pull *model* (download it if not present).

        This is a **blocking** call that may take several minutes on first run.
        AURa routes it through a background CPU task so the shell stays
        responsive.

        Returns True on success, False on error.
        """
        target = model or self._model
        _logger.info("Pulling Ollama model '%s' — this may take several minutes…", target)
        try:
            payload = json.dumps({"name": target, "stream": False}).encode()
            req = urllib.request.Request(
                f"{self._base_url}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # Pull can take a long time — use a very long timeout
            with urllib.request.urlopen(req, timeout=3600) as resp:
                data = json.loads(resp.read().decode())
            ok = data.get("status") in ("success", "pulling manifest")
            _logger.info("Pull %s: status=%s", target, data.get("status"))
            return ok
        except Exception as exc:
            _logger.error("OllamaBackend.pull_model error: %s", exc)
            return False

    def server_version(self) -> str:
        """Return the Ollama server version string, or empty string if unreachable."""
        try:
            req = urllib.request.Request(f"{self._base_url}/api/version")
            with urllib.request.urlopen(req, timeout=_HEALTH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            return data.get("version", "unknown")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _server_up(self) -> bool:
        """Quick check — is the Ollama HTTP server reachable at all?"""
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=_HEALTH_TIMEOUT):
                pass
            return True
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url
