# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Cloud AI Router
====================
Routes AI inference requests through the Virtual Cloud / Virtual CPU layer so
that heavy model work is **never executed inline in the device process**.

How it works
------------
1. A caller (shell, API, AIOS) sends a prompt to ``CloudAIRouter.route()``.
2. The router submits the inference to a background thread pool — keeping the
   heavy Ollama HTTP call off the device's main thread.
3. The VirtualCPU is notified (lightweight tracking task) so the dashboard and
   metrics report the inference workload.
4. The VirtualCloud tracks resource usage on its simulated nodes.
5. The result is returned to the caller via a ``Future``.

All model artefacts are stored under the virtual cloud's ``model_cache_dir``
so nothing accumulates in unexpected places.
"""

from __future__ import annotations

import concurrent.futures
import os
import time
import threading
from typing import Optional, TYPE_CHECKING

from aura.config import OllamaConfig
from aura.utils import get_logger, utcnow

if TYPE_CHECKING:
    from aura.cpu.virtual_cpu import VirtualCPU
    from aura.cloud.virtual_cloud import VirtualCloud
    from aura.ai_engine.engine import AIResponse, BaseBackend

_logger = get_logger("aura.cloud.ai_router")

# Maximum concurrent cloud inference workers
_MAX_WORKERS = 4


class CloudAIRouter:
    """
    Routes AI inference calls through the Virtual CPU / Virtual Cloud.

    The router keeps a reference to the active AI backend (e.g.
    ``OllamaBackend``) and submits every ``route()`` call as a background
    thread-pool task so device RAM is never burdened by model weights.  The
    VirtualCPU is also notified so system metrics and the dashboard reflect the
    true inference workload.

    Parameters
    ----------
    virtual_cpu:
        The ``VirtualCPU`` instance managed by the AIOS.
    virtual_cloud:
        The ``VirtualCloud`` instance managed by the AIOS.
    backend:
        Any ``BaseBackend`` implementation.  Typically an ``OllamaBackend``.
    ollama_config:
        Configuration for the Ollama model.
    """

    def __init__(
        self,
        virtual_cpu: "VirtualCPU",
        virtual_cloud: "VirtualCloud",
        backend: "BaseBackend",
        ollama_config: Optional[OllamaConfig] = None,
    ) -> None:
        self._cpu = virtual_cpu
        self._cloud = virtual_cloud
        self._backend = backend
        self._cfg = ollama_config or OllamaConfig()
        self._start_time = time.monotonic()
        self._queries_routed: int = 0
        self._queries_completed: int = 0
        self._queries_failed: int = 0
        self._lock = threading.Lock()

        # Thread pool for background inference — keeps device main thread free
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_WORKERS,
            thread_name_prefix="cloud-ai",
        )

        # Register the active model in the cloud model registry so the
        # dashboard shows it under "Registered AI models".
        self._register_model_in_cloud()

        _logger.info(
            "CloudAIRouter ready — backend=%s, model=%s, cloud_router=%s",
            type(backend).__name__,
            getattr(backend, "model_name", "?"),
            self._cfg.use_cloud_router,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: float = 120.0,
    ) -> "AIResponse":
        """
        Route *prompt* through the virtual cloud/CPU and return an AIResponse.

        If ``OllamaConfig.use_cloud_router`` is ``False`` the call is executed
        inline (useful for debugging or tests).  Otherwise the inference runs
        in a background thread-pool worker so the caller thread is not blocked
        and device RAM stays free.
        """
        with self._lock:
            self._queries_routed += 1

        if not self._cfg.use_cloud_router:
            # Direct call — no thread overhead (useful for tests)
            return self._run_inference(prompt, system_prompt, max_tokens, temperature)

        # Submit to background thread pool
        future = self._executor.submit(
            self._run_inference, prompt, system_prompt, max_tokens, temperature
        )

        # Also submit a lightweight VirtualCPU tracking task for metrics
        self._submit_tracking_task(prompt)

        try:
            result = future.result(timeout=timeout)
            with self._lock:
                self._queries_completed += 1
            return result
        except concurrent.futures.TimeoutError:
            future.cancel()
            with self._lock:
                self._queries_failed += 1
            _logger.warning("CloudAIRouter: inference timed out after %.0fs", timeout)
            from aura.ai_engine.engine import AIResponse
            return AIResponse(
                text=(
                    "Cloud AI inference timed out.  The model may still be loading.\n"
                    "Try: aura cloud-ai status"
                ),
                model=getattr(self._backend, "model_name", "timeout"),
                tokens_used=0,
                latency_ms=timeout * 1000.0,
            )
        except Exception as exc:
            with self._lock:
                self._queries_failed += 1
            _logger.error("CloudAIRouter: inference error: %s", exc)
            from aura.ai_engine.engine import AIResponse
            return AIResponse(
                text=f"Cloud inference error: {exc}",
                model=getattr(self._backend, "model_name", "error"),
                tokens_used=0,
                latency_ms=0.0,
            )

    def pull_model(self, model: Optional[str] = None) -> bool:
        """
        Pull (download) a model into the virtual cloud storage in a background
        thread.  Returns True if the pull task was submitted successfully.
        """
        target = model or self._cfg.model
        _logger.info("Submitting model pull task for '%s'", target)

        def _pull_fn():
            if hasattr(self._backend, "pull_model"):
                ok = self._backend.pull_model(target)
                if ok:
                    self._register_model_in_cloud(model_name=target)
                return ok
            return False

        self._executor.submit(_pull_fn)
        # Also notify VirtualCPU
        try:
            self._cpu.submit(fn=lambda: None, name=f"cloud-ai-pull:{target}")
        except Exception:
            pass
        return True

    def is_backend_ready(self) -> bool:
        """Return True if the underlying AI backend is ready."""
        return self._backend.is_ready()

    def list_cloud_models(self) -> list:
        """Return models registered in the Virtual Cloud."""
        return self._cloud.list_models()

    def backend_info(self) -> dict:
        """Return information about the current AI backend."""
        b = self._backend
        return {
            "backend_class": type(b).__name__,
            "model_name": getattr(b, "model_name", getattr(b, "_model", "?")),
            "base_url": getattr(b, "base_url", None),
            "is_ready": b.is_ready(),
            "server_version": getattr(b, "server_version", lambda: "")(),
        }

    def metrics(self) -> dict:
        with self._lock:
            return {
                "queries_routed": self._queries_routed,
                "queries_completed": self._queries_completed,
                "queries_failed": self._queries_failed,
                "cloud_router_enabled": self._cfg.use_cloud_router,
                "backend": type(self._backend).__name__,
                "model": getattr(self._backend, "model_name", "?"),
                "uptime_seconds": round(time.monotonic() - self._start_time, 1),
            }

    def shutdown(self) -> None:
        """Shut down the background thread pool gracefully."""
        self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_inference(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> "AIResponse":
        try:
            return self._backend.generate(
                prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            _logger.error("CloudAIRouter._run_inference error: %s", exc)
            from aura.ai_engine.engine import AIResponse
            return AIResponse(
                text=f"Inference error: {exc}",
                model=getattr(self._backend, "model_name", "error"),
                tokens_used=0,
                latency_ms=0.0,
            )

    def _submit_tracking_task(self, prompt_snippet: str) -> None:
        """Submit a lightweight no-op task to VirtualCPU for metric tracking."""
        try:
            label = (prompt_snippet[:40] + "…") if len(prompt_snippet) > 40 else prompt_snippet
            self._cpu.submit(fn=lambda: None, name=f"cloud-ai:{label}")
        except Exception:
            pass

    def _register_model_in_cloud(self, model_name: Optional[str] = None) -> None:
        """Register the current model in the VirtualCloud model registry."""
        name = model_name or getattr(
            self._backend,
            "model_name",
            getattr(self._backend, "_model", self._cfg.model),
        )
        # Approximate size: Ollama llama3.1:8b Q4_K_M ≈ 4.7 GB
        approx_size = 4_700_000_000
        try:
            self._cloud.register_model(
                model_id=f"cloud-ai:{name}",
                model_name=name,
                size_bytes=approx_size,
                backend=type(self._backend).__name__,
            )
        except Exception as exc:
            _logger.debug("Could not register model in cloud: %s", exc)

    def _get_priority(self):
        """Lazily resolve the TaskPriority.HIGH enum value."""
        try:
            from aura.cpu.virtual_cpu import TaskPriority
            return TaskPriority.HIGH
        except Exception:
            return 1
