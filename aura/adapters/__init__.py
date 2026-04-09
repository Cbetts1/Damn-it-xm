"""AURa Adapters — platform detection and cross-platform subprocess bridge."""
from aura.adapters.android_bridge import detect_capabilities, AndroidBridge

__all__ = ["detect_capabilities", "AndroidBridge"]
