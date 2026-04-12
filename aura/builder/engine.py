# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Builder — self-expansion engine."""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

from aura.utils import get_logger, utcnow
from aura.builder.templates import ModuleTemplate, ScriptTemplate, ConfigTemplate

_logger = get_logger("aura.builder.engine")

_DEFAULT_OUTPUT_DIR = os.path.expanduser("~/.aura/builder")


class BuilderEngine:
    """
    Generates and records new AURa modules, scripts, and config files.

    All artefacts are written to *output_dir* (default: ``~/.aura/builder``).
    The engine keeps an in-memory manifest of every file it has produced.
    """

    def __init__(
        self,
        output_dir: str = "",
        registry: Optional[Any] = None,
    ) -> None:
        self._output_dir = output_dir or _DEFAULT_OUTPUT_DIR
        self._registry = registry
        self._lock = threading.RLock()
        self._artefacts: List[dict] = []
        self._modules_generated: int = 0
        self._scripts_generated: int = 0
        self._configs_generated: int = 0
        os.makedirs(self._output_dir, exist_ok=True)
        _logger.info("BuilderEngine: output_dir=%s", self._output_dir)

    # ------------------------------------------------------------------
    # Generator methods
    # ------------------------------------------------------------------

    def generate_module(self, name: str, description: str = "") -> str:
        """Render and write a Python module skeleton. Returns the file path."""
        content = ModuleTemplate(name, description).render()
        filename = f"{name.replace('-', '_')}.py"
        path = self._write(filename, content)
        with self._lock:
            self._modules_generated += 1
            self._artefacts.append(
                {"name": name, "path": path, "type": "module", "created_at": utcnow()}
            )
        _logger.info("BuilderEngine: module generated: %s", path)
        return path

    def generate_script(self, name: str, description: str = "") -> str:
        """Render and write a POSIX shell script. Returns the file path."""
        content = ScriptTemplate(name, description).render()
        filename = f"{name.replace('-', '_')}.sh"
        path = self._write(filename, content)
        with self._lock:
            self._scripts_generated += 1
            self._artefacts.append(
                {"name": name, "path": path, "type": "script", "created_at": utcnow()}
            )
        _logger.info("BuilderEngine: script generated: %s", path)
        return path

    def generate_config(self, name: str, defaults: Optional[dict] = None) -> str:
        """Render and write a JSON config file. Returns the file path."""
        content = ConfigTemplate(name, defaults).render()
        filename = f"{name.replace('-', '_')}.json"
        path = self._write(filename, content)
        with self._lock:
            self._configs_generated += 1
            self._artefacts.append(
                {"name": name, "path": path, "type": "config", "created_at": utcnow()}
            )
        _logger.info("BuilderEngine: config generated: %s", path)
        return path

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_generated(self) -> List[dict]:
        """Return a copy of the artefact manifest."""
        with self._lock:
            return [dict(a) for a in self._artefacts]

    def metrics(self) -> dict:
        with self._lock:
            return {
                "output_dir": self._output_dir,
                "modules_generated": self._modules_generated,
                "scripts_generated": self._scripts_generated,
                "configs_generated": self._configs_generated,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, filename: str, content: str) -> str:
        path = os.path.join(self._output_dir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path
