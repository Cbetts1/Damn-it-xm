# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Branding — Boot Banner & Identity
"""


def get_boot_banner(version: str = "2.0.0") -> str:
    """Return a multi-line ASCII art boot banner string."""
    return (
        "\n"
        "    ___   __  ______  ___\n"
        "   / _ | / / / / __ \\/   |\n"
        "  / __ |/ /_/ / /_/ / /| |\n"
        " /_/ |_|\\____/\\____/_/ |_|\n"
        "\n"
        " A I - N A T I V E   O S\n"
        f" Version {version}\n"
        " (c) 2024-2026 AURa Project\n"
    )


def get_identity_info() -> dict:
    """Return a dict of AURA identity metadata."""
    return {
        "name": "AURA",
        "full_name": "Autonomous Universal Resource Architecture",
        "version": "2.0.0",
        "tagline": "AI-Native Operating System",
        "author": "AURa Project",
        "year": "2024-2026",
        "license": "MIT",
    }
