# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Adapters — platform detection and cross-platform subprocess bridge."""
from aura.adapters.android_bridge import detect_capabilities, AndroidBridge
from aura.adapters.linux_bridge import LinuxBridge
from aura.adapters.macos_bridge import MacOSBridge

__all__ = ["detect_capabilities", "AndroidBridge", "LinuxBridge", "MacOSBridge"]
