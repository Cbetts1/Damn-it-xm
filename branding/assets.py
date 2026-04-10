# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Branding Assets
====================
Brand colours, logo text, taglines, and HTML badge helpers.
"""


class BrandingAssets:
    """Static branding assets for the AURa project."""

    PRIMARY_COLOR = "#6C63FF"
    SECONDARY_COLOR = "#2D2B55"
    ACCENT_COLOR = "#00D4FF"

    @classmethod
    def get_color_palette(cls) -> dict:
        """Return the full AURA colour palette."""
        return {
            "primary": cls.PRIMARY_COLOR,
            "secondary": cls.SECONDARY_COLOR,
            "accent": cls.ACCENT_COLOR,
            "background": "#1A1A2E",
            "text": "#E0E0E0",
        }

    @classmethod
    def get_logo_text(cls) -> str:
        """Return a simple text logo."""
        return "[ AURA ]"

    @classmethod
    def get_tagline(cls) -> str:
        """Return the AURA tagline."""
        return "AI-Native Operating System"

    @classmethod
    def get_html_badge(cls) -> str:
        """Return a simple HTML badge string."""
        return (
            f'<span style="'
            f"background:{cls.PRIMARY_COLOR};"
            f"color:#FFFFFF;"
            f"padding:2px 8px;"
            f"border-radius:4px;"
            f'font-family:monospace;">'
            f"AURA"
            f"</span>"
        )
