# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Personality Kernel
=======================
Manages the AI assistant's personality profile — tone, empathy, verbosity,
technical depth, and the generated system prompt.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from aura.utils import get_logger

_logger = get_logger("aura.ai_engine.personality")


class PersonalityKernel:
    """Encapsulates AURA's personality profile and prompt generation logic."""

    DEFAULT_PROFILE: dict = {
        "name": "AURA",
        "tone": "professional",
        "verbosity": 5,
        "empathy": 7,
        "technical_depth": 8,
        "language": "en",
        "system_prompt": "You are AURA, an AI-native OS assistant.",
        "traits": ["helpful", "precise", "security-conscious"],
    }

    def __init__(self, profile: Optional[dict] = None) -> None:
        self._profile: dict = copy.deepcopy(profile if profile is not None else self.DEFAULT_PROFILE)
        _logger.debug("PersonalityKernel initialised with profile name='%s'.", self._profile.get("name"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        """Return the system prompt from the current profile."""
        return str(self._profile.get("system_prompt", ""))

    def update_trait(self, key: str, value: Any) -> None:
        """Update a profile key with *value*."""
        old = self._profile.get(key)
        self._profile[key] = value
        _logger.debug("Trait '%s' updated: %r -> %r.", key, old, value)

    def get_trait(self, key: str) -> Any:
        """Return the profile value for *key*, or None if not present."""
        return self._profile.get(key)

    def apply_to_prompt(self, user_prompt: str) -> str:
        """Prepend system-prompt context to *user_prompt*."""
        system_prompt = self.get_system_prompt()
        if not system_prompt:
            return user_prompt
        return f"{system_prompt}\n\n{user_prompt}"

    def to_dict(self) -> dict:
        """Return a deep copy of the full profile."""
        return copy.deepcopy(self._profile)

    def reset(self) -> None:
        """Reset the profile to DEFAULT_PROFILE."""
        self._profile = copy.deepcopy(self.DEFAULT_PROFILE)
        _logger.info("PersonalityKernel reset to DEFAULT_PROFILE.")
