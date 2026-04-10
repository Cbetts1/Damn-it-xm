# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Model Scanner
==================
Scans filesystem directories for AI model files and collects metadata.
Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.ai_engine.model_scanner")

_MODEL_EXTENSIONS = {".gguf", ".bin", ".pt", ".safetensors"}

_BACKEND_MAP: Dict[str, str] = {
    ".gguf": "llama",
    ".bin": "transformers",
    ".pt": "transformers",
    ".safetensors": "transformers",
}


class ModelScanner:
    """Scans directories for AI model files and returns structured metadata."""

    def __init__(self, scan_dirs: Optional[List[str]] = None) -> None:
        self.scan_dirs: List[str] = list(scan_dirs or [])
        self.scan_result: List[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> List[dict]:
        """Walk all scan_dirs and return metadata for discovered model files."""
        results: List[dict] = []
        detected_at = utcnow()

        for directory in self.scan_dirs:
            if not os.path.isdir(directory):
                _logger.warning("scan: directory does not exist: %s", directory)
                continue
            for root, _dirs, files in os.walk(directory):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in _MODEL_EXTENSIONS:
                        continue
                    full_path = os.path.join(root, filename)
                    try:
                        size_bytes = os.path.getsize(full_path)
                    except OSError as exc:
                        _logger.warning("scan: cannot stat '%s': %s", full_path, exc)
                        size_bytes = 0
                    results.append(
                        {
                            "path": full_path,
                            "name": os.path.splitext(filename)[0],
                            "extension": ext,
                            "size_bytes": size_bytes,
                            "detected_at": detected_at,
                        }
                    )

        _logger.info("scan: found %d model file(s) across %d dir(s).", len(results), len(self.scan_dirs))
        self.scan_result = results
        return results

    def detect_backend(self, file_path: str) -> str:
        """Return the likely backend for a given model file path."""
        ext = os.path.splitext(file_path)[1].lower()
        return _BACKEND_MAP.get(ext, "unknown")

    def clear_cache(self) -> None:
        """Clear the cached scan result."""
        self.scan_result = []
        _logger.debug("scan_result cache cleared.")
