# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa LLaMA Backend (stub)
=========================
Integrates llama.cpp (via the llama_cpp Python binding) as an AI inference
backend.  When llama_cpp is not installed or no model_path is provided, all
calls return a graceful stub response so the rest of AURa continues to work.
"""

from __future__ import annotations

import os
import time

from aura.config import AIEngineConfig
from aura.ai_engine.engine import AIResponse
from aura.utils import get_logger

_logger = get_logger("aura.ai_engine.llama")

_STUB_TEXT = (
    "LLaMA backend not available - model_path not set or llama_cpp not installed"
)


def _llama_cpp_available() -> bool:
    """Return True if the llama_cpp package can be imported."""
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False


class LlamaBackend:
    """
    llama.cpp-powered inference backend.

    This is a *stub* that wires in llama_cpp when the library is present
    and a valid model_path is supplied.  Without those prerequisites the
    backend reports itself as not-ready and returns a stub AIResponse so
    the rest of AURa degrades gracefully.
    """

    def __init__(self, config: AIEngineConfig, model_path: str = "") -> None:
        self._config = config
        self._model_path = model_path
        self._llm = None  # lazy-loaded llama_cpp.Llama instance
        _logger.debug(
            "LlamaBackend created (model_path=%r, llama_cpp=%s).",
            model_path,
            _llama_cpp_available(),
        )

    # ------------------------------------------------------------------
    # Backend interface
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return True only when model_path exists AND llama_cpp is importable."""
        return bool(self._model_path) and os.path.isfile(self._model_path) and _llama_cpp_available()

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> AIResponse:
        """
        Generate a response for *prompt*.

        Uses llama_cpp when ready; otherwise returns a stub response.
        """
        start = time.monotonic()

        if not self.is_ready():
            _logger.warning("LlamaBackend.generate: backend not ready — returning stub.")
            return AIResponse(
                text=_STUB_TEXT,
                model="llama-stub",
                tokens_used=0,
                latency_ms=0.0,
            )

        try:
            import llama_cpp  # noqa: F811

            if self._llm is None:
                _logger.info("Loading LLaMA model from '%s'.", self._model_path)
                self._llm = llama_cpp.Llama(
                    model_path=self._model_path,
                    n_ctx=self._config.max_tokens,
                )

            output = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = output["choices"][0]["text"]
            tokens_used = output.get("usage", {}).get("total_tokens", 0)
            latency_ms = (time.monotonic() - start) * 1000.0
            _logger.debug("LlamaBackend generated %d token(s) in %.0f ms.", tokens_used, latency_ms)
            return AIResponse(
                text=text,
                model=os.path.basename(self._model_path),
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )

        except Exception as exc:
            _logger.error("LlamaBackend.generate error: %s", exc)
            return AIResponse(
                text=f"LLaMA backend error: {exc}",
                model="llama-error",
                tokens_used=0,
                latency_ms=(time.monotonic() - start) * 1000.0,
            )
