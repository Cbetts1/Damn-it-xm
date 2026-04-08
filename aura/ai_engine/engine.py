"""
AURa AI Engine
==============
Pluggable AI inference backend supporting:
  - "builtin"          : Built-in rule/template engine (no dependencies, works offline)
  - "transformers"     : Hugging Face Transformers (free open-source models)
  - "openai_compatible": Any OpenAI-compatible API (LM Studio, Ollama, text-generation-webui…)

The engine is the "brain" of AURa — the AI OS delegates queries, task planning,
and system decisions to it.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Generator, List, Optional

from aura.config import AIEngineConfig
from aura.utils import get_logger

_logger = get_logger("aura.ai_engine")

# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

class AIResponse:
    """Structured response from the AI engine."""

    def __init__(
        self,
        text: str,
        model: str = "unknown",
        tokens_used: int = 0,
        latency_ms: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> None:
        self.text = text
        self.model = model
        self.tokens_used = tokens_used
        self.latency_ms = latency_ms
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"AIResponse(model={self.model!r}, tokens={self.tokens_used}, latency={self.latency_ms:.0f}ms)"


# ---------------------------------------------------------------------------
# Abstract base backend
# ---------------------------------------------------------------------------

class BaseBackend(ABC):
    """Abstract AI backend interface."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> AIResponse:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...

    def stream(self, prompt: str, system_prompt: str = "", **kwargs) -> Generator[str, None, None]:
        """Default streaming: yield entire response as one chunk."""
        yield self.generate(prompt, system_prompt, **kwargs).text


# ---------------------------------------------------------------------------
# Built-in backend (no external dependencies)
# ---------------------------------------------------------------------------

_BUILTIN_KNOWLEDGE: dict = {
    # System commands
    r"status|health": "All AURa virtual components are operational.\n"
        "  • AI OS     : Running\n"
        "  • Virtual Cloud : Online  (8 nodes)\n"
        "  • Virtual CPU   : Active  (64 vCores @ 4.2 GHz)\n"
        "  • Virtual Server: Serving (port 8000)",
    r"help": "AURa commands:\n"
        "  status   — system health overview\n"
        "  cloud    — virtual cloud operations\n"
        "  cpu      — virtual CPU metrics\n"
        "  server   — virtual server management\n"
        "  ask      — query the AI engine\n"
        "  models   — list available AI models\n"
        "  history  — show session history\n"
        "  clear    — clear the terminal\n"
        "  exit     — quit AURa shell",
    r"cloud": "Virtual Cloud:\n"
        "  Storage : 1024 GB  (used: 0 GB)\n"
        "  Nodes   : 8 active\n"
        "  Region  : virtual-us-east-1\n"
        "  CDN     : enabled\n"
        "  Models  : cached in ~/.aura/model_cache",
    r"cpu": "Virtual CPU:\n"
        "  Architecture : AURa-v1\n"
        "  vCores       : 64 (128 threads)\n"
        "  Clock        : 4.2 GHz\n"
        "  L3 Cache     : 128 MB\n"
        "  Load         : 2% (nearly idle)",
    r"server": "Virtual Server:\n"
        "  Status  : Running\n"
        "  Host    : 0.0.0.0:8000\n"
        "  Workers : 4\n"
        "  Routes  : /api/v1/*  /health  /dashboard",
    r"model|ai|what are you": "I am AURa — Autonomous Universal Resource Architecture.\n"
        "I am the AI OS and intelligence layer of this virtual system.\n"
        "I oversee the Virtual Cloud, Virtual CPU, and Virtual Server.\n"
        "I am built on free open-source AI technology.",
    r"hello|hi|hey|greet": "Hello! I'm AURa, your AI OS. How can I assist you today?\n"
        "Type 'help' for a list of commands.",
    r"version": "AURa v1.0.0 — ready for release.",
}


class BuiltinBackend(BaseBackend):
    """
    Deterministic rule-based backend.
    Works with zero dependencies — perfect for offline use or as a fallback.
    """

    def __init__(self, config: AIEngineConfig) -> None:
        self._config = config
        _logger.info("Builtin AI backend initialised")

    def is_ready(self) -> bool:
        return True

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> AIResponse:
        t0 = time.monotonic()
        lower = prompt.lower().strip()

        for pattern, reply in _BUILTIN_KNOWLEDGE.items():
            if re.search(pattern, lower):
                return AIResponse(
                    text=reply,
                    model="aura-builtin-1.0",
                    tokens_used=len(prompt.split()),
                    latency_ms=(time.monotonic() - t0) * 1000,
                )

        # Fallback — thoughtful generic response
        fallback = (
            f"AURa understood your request: '{prompt}'\n"
            "Processing through the AI OS… The virtual components are analysing your input.\n"
            "For richer responses, configure a Hugging Face or OpenAI-compatible backend:\n"
            "  export AURA_AI_BACKEND=transformers\n"
            "  export AURA_MODEL_NAME=microsoft/DialoGPT-medium"
        )
        return AIResponse(
            text=fallback,
            model="aura-builtin-1.0",
            tokens_used=len(prompt.split()),
            latency_ms=(time.monotonic() - t0) * 1000,
        )


# ---------------------------------------------------------------------------
# Transformers backend (Hugging Face — free & open-source)
# ---------------------------------------------------------------------------

class TransformersBackend(BaseBackend):
    """
    Hugging Face Transformers inference backend.
    Supports any text-generation model from HuggingFace Hub.

    Popular free open-source choices:
      - microsoft/DialoGPT-medium      (conversational, ~350 MB)
      - tiiuae/falcon-rw-1b            (general, ~2.6 GB)
      - mistralai/Mistral-7B-Instruct  (powerful, ~14 GB)
      - meta-llama/Llama-2-7b-chat-hf  (powerful, ~13 GB, requires HF token)
    """

    def __init__(self, config: AIEngineConfig) -> None:
        self._config = config
        self._pipeline = None
        self._tokenizer = None
        self._model = None
        self._ready = False
        self._load_model()

    def _load_model(self) -> None:
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch

            _logger.info("Loading model '%s' on %s …", self._config.model_name, self._config.device)
            device_id = 0 if self._config.device == "cuda" else -1

            self._pipeline = pipeline(
                "text-generation",
                model=self._config.model_name,
                device=device_id,
                trust_remote_code=True,
            )
            self._ready = True
            _logger.info("Model '%s' loaded successfully", self._config.model_name)
        except ImportError:
            _logger.warning(
                "transformers/torch not installed. "
                "Run: pip install transformers torch  — falling back to builtin backend."
            )
        except Exception as exc:
            _logger.error("Failed to load model '%s': %s", self._config.model_name, exc)

    def is_ready(self) -> bool:
        return self._ready

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> AIResponse:
        if not self._ready or self._pipeline is None:
            return AIResponse(
                text="[Transformers backend not ready — check logs]",
                model=self._config.model_name,
            )
        t0 = time.monotonic()
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        outputs = self._pipeline(
            full_prompt,
            max_new_tokens=self._config.max_tokens,
            temperature=self._config.temperature,
            do_sample=True,
            pad_token_id=self._pipeline.tokenizer.eos_token_id,
        )
        generated = outputs[0]["generated_text"]
        # Strip the prompt prefix from the output
        if generated.startswith(full_prompt):
            generated = generated[len(full_prompt):].strip()
        return AIResponse(
            text=generated or "[empty response]",
            model=self._config.model_name,
            tokens_used=len(full_prompt.split()) + len(generated.split()),
            latency_ms=(time.monotonic() - t0) * 1000,
        )


# ---------------------------------------------------------------------------
# OpenAI-compatible backend (Ollama, LM Studio, text-generation-webui, …)
# ---------------------------------------------------------------------------

class OpenAICompatibleBackend(BaseBackend):
    """
    Backend for any OpenAI-compatible HTTP API.
    Works with: Ollama (localhost:11434), LM Studio, text-generation-webui, etc.
    All free & open-source server solutions.
    """

    _SYSTEM_PROMPT = (
        "You are AURa (Autonomous Universal Resource Architecture), "
        "an AI OS that oversees a Virtual Cloud, Virtual CPU, and Virtual Server. "
        "You are helpful, precise, and technically knowledgeable."
    )

    def __init__(self, config: AIEngineConfig) -> None:
        self._config = config
        self._ready = False
        self._base_url = config.api_base_url or "http://localhost:11434/v1"
        self._api_key = config.api_key or "sk-none"
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import httpx
            self._client = httpx.Client(base_url=self._base_url, timeout=60.0)
            self._ready = True
            _logger.info("OpenAI-compatible backend ready at %s", self._base_url)
        except ImportError:
            _logger.warning("httpx not installed. Run: pip install httpx")

    def is_ready(self) -> bool:
        return self._ready

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> AIResponse:
        if not self._ready or self._client is None:
            return AIResponse(text="[OpenAI-compatible backend not ready]", model=self._config.model_name)
        t0 = time.monotonic()
        sys_msg = system_prompt or self._SYSTEM_PROMPT
        payload = {
            "model": self._config.model_name,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            resp = self._client.post("/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
        except Exception as exc:
            _logger.error("API call failed: %s", exc)
            text = f"[API error: {exc}]"
            tokens = 0
        return AIResponse(
            text=text,
            model=self._config.model_name,
            tokens_used=tokens,
            latency_ms=(time.monotonic() - t0) * 1000,
        )


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def create_backend(config: AIEngineConfig) -> BaseBackend:
    backend_map = {
        "builtin": BuiltinBackend,
        "transformers": TransformersBackend,
        "openai_compatible": OpenAICompatibleBackend,
    }
    cls = backend_map.get(config.backend, BuiltinBackend)
    _logger.info("Creating AI backend: %s", cls.__name__)
    return cls(config)


# ---------------------------------------------------------------------------
# High-level AIEngine class
# ---------------------------------------------------------------------------

class AIEngine:
    """
    The AURa AI Engine.
    Manages the active backend, session context, and exposes a simple API
    that the AI OS and Shell use to interact with the AI model.
    """

    SYSTEM_PROMPT = (
        "You are AURa (Autonomous Universal Resource Architecture) — "
        "an intelligent AI OS responsible for orchestrating a Virtual Cloud, "
        "Virtual CPU, and Virtual Server. "
        "You are precise, helpful, and technically expert. "
        "Respond concisely unless asked for detailed explanations."
    )

    def __init__(self, config: AIEngineConfig) -> None:
        self._config = config
        self._backend: BaseBackend = create_backend(config)
        self._history: List[dict] = []
        self._logger = get_logger("aura.ai_engine")

    @property
    def backend_name(self) -> str:
        return type(self._backend).__name__

    @property
    def model_name(self) -> str:
        return self._config.model_name

    def is_ready(self) -> bool:
        return self._backend.is_ready()

    def ask(self, prompt: str, context: Optional[str] = None) -> AIResponse:
        """Send a query to the AI engine and return a response."""
        sys_prompt = f"{self.SYSTEM_PROMPT}\n\n{context}" if context else self.SYSTEM_PROMPT
        response = self._backend.generate(prompt, system_prompt=sys_prompt)
        self._history.append({"role": "user", "content": prompt})
        self._history.append({"role": "assistant", "content": response.text})
        return response

    def plan_task(self, task_description: str) -> AIResponse:
        """Ask the AI to produce a step-by-step execution plan for a task."""
        prompt = (
            f"Create a detailed step-by-step execution plan for the following task "
            f"within the AURa virtual system:\n\n{task_description}\n\n"
            "Format each step as: Step N: <action>"
        )
        return self.ask(prompt)

    def analyse_metrics(self, metrics: dict) -> AIResponse:
        """Ask the AI to analyse system metrics and make recommendations."""
        metrics_str = json.dumps(metrics, indent=2)
        prompt = (
            f"Analyse these AURa system metrics and provide recommendations:\n\n{metrics_str}"
        )
        return self.ask(prompt)

    def clear_history(self) -> None:
        self._history.clear()

    def get_history(self) -> List[dict]:
        return list(self._history)
