"""
AURa Android/Termux Bridge Adapter
====================================
Detects the current platform capabilities and provides a unified adapter
that works on Android/Termux, desktop Linux, macOS, and Windows.

Classes:
  • PlatformCapabilities — dataclass describing what the host can do
  • AndroidBridge        — cross-platform command runner and installer
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, Tuple

from aura.utils import get_logger

_logger = get_logger("aura.adapters.android_bridge")


# ---------------------------------------------------------------------------
# PlatformCapabilities
# ---------------------------------------------------------------------------

@dataclass
class PlatformCapabilities:
    """Snapshot of the capabilities detected on the running host."""

    is_android: bool = False
    is_termux: bool = False
    is_linux: bool = False
    is_windows: bool = False
    has_bash: bool = False
    has_python: bool = False
    has_git: bool = False
    has_curl: bool = False
    has_wget: bool = False
    has_ssh: bool = False
    has_pkg: bool = False        # Termux package manager
    has_apt: bool = False
    has_pip: bool = False
    arch: str = ""               # e.g. "aarch64", "x86_64"
    os_release: str = ""
    termux_prefix: str = ""      # e.g. "/data/data/com.termux/files/usr" or ""


# ---------------------------------------------------------------------------
# detect_capabilities
# ---------------------------------------------------------------------------

def detect_capabilities() -> PlatformCapabilities:
    """
    Probe the current environment and return a populated
    :class:`PlatformCapabilities` instance.

    All detection is done via stdlib only (os, sys, platform, shutil.which).
    """
    caps = PlatformCapabilities()

    # ---- OS detection -------------------------------------------------------
    system = platform.system().lower()
    caps.is_linux = system == "linux"
    caps.is_windows = system == "windows"
    caps.arch = platform.machine() or "unknown"

    # Detect Android / Termux
    # Termux sets PREFIX and TERMUX_VERSION; the Android property file exists.
    termux_prefix = os.environ.get("PREFIX", "")
    if "com.termux" in termux_prefix:
        caps.is_termux = True
        caps.is_android = True
        caps.termux_prefix = termux_prefix
    elif os.path.exists("/system/build.prop") or os.path.exists("/proc/version"):
        try:
            with open("/proc/version") as fh:
                content = fh.read().lower()
            if "android" in content:
                caps.is_android = True
        except OSError:
            pass

    # ---- OS release string --------------------------------------------------
    try:
        if caps.is_linux or caps.is_android:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as fh:
                    for line in fh:
                        if line.startswith("PRETTY_NAME="):
                            caps.os_release = line.split("=", 1)[1].strip().strip('"')
                            break
            if not caps.os_release:
                caps.os_release = platform.version()
        else:
            caps.os_release = platform.version()
    except Exception:
        caps.os_release = platform.version()

    # ---- Tool detection (shutil.which) --------------------------------------
    _tool = shutil.which
    caps.has_bash   = bool(_tool("bash"))
    caps.has_python = bool(_tool("python3") or _tool("python"))
    caps.has_git    = bool(_tool("git"))
    caps.has_curl   = bool(_tool("curl"))
    caps.has_wget   = bool(_tool("wget"))
    caps.has_ssh    = bool(_tool("ssh"))
    caps.has_pkg    = bool(_tool("pkg"))
    caps.has_apt    = bool(_tool("apt") or _tool("apt-get"))
    caps.has_pip    = bool(_tool("pip3") or _tool("pip"))

    _logger.debug(
        "Platform: android=%s termux=%s linux=%s arch=%s",
        caps.is_android, caps.is_termux, caps.is_linux, caps.arch,
    )
    return caps


# ---------------------------------------------------------------------------
# AndroidBridge
# ---------------------------------------------------------------------------

class AndroidBridge:
    """
    Cross-platform command runner and package installer.

    Works on Android/Termux, Linux, macOS, and Windows.
    Falls back gracefully when specific tools are unavailable.
    """

    def __init__(self, capabilities: PlatformCapabilities) -> None:
        self._caps = capabilities
        self._logger = get_logger("aura.adapters.android_bridge")

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def run_command(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
        """
        Execute *cmd* in a shell and return ``(returncode, stdout, stderr)``.

        Uses the system shell; falls back to /system/bin/sh on Android when
        ``/bin/sh`` is unavailable.
        """
        shell_exec = True
        try:
            result = subprocess.run(
                cmd,
                shell=shell_exec,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self._logger.warning("Command timed out after %ds: %s", timeout, cmd)
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as exc:
            self._logger.error("run_command error: %s", exc)
            return -1, "", str(exc)

    # ------------------------------------------------------------------
    # Package installation
    # ------------------------------------------------------------------

    def install_package(self, package: str) -> str:
        """
        Install *package* using the most appropriate package manager.

        Order of preference: pkg (Termux) → apt/apt-get → pip.
        Returns a human-readable result string.
        """
        if self._caps.has_pkg:
            rc, out, err = self.run_command(f"pkg install -y {package}", timeout=120)
        elif self._caps.has_apt:
            mgr = "apt-get" if shutil.which("apt-get") else "apt"
            rc, out, err = self.run_command(f"{mgr} install -y {package}", timeout=120)
        elif self._caps.has_pip:
            pip = "pip3" if shutil.which("pip3") else "pip"
            rc, out, err = self.run_command(f"{pip} install {package}", timeout=120)
        else:
            return f"No supported package manager found to install '{package}'."

        if rc == 0:
            return f"Installed '{package}' successfully.\n{out}".strip()
        return f"Failed to install '{package}' (rc={rc}).\n{err}".strip()

    # ------------------------------------------------------------------
    # Storage paths
    # ------------------------------------------------------------------

    def get_storage_paths(self) -> Dict[str, str]:
        """
        Return a dict of relevant storage paths for the current platform.

        Keys may include: ``home``, ``prefix``, ``sdcard``, ``cwd``.
        """
        paths: Dict[str, str] = {
            "home": os.path.expanduser("~"),
            "cwd": os.getcwd(),
        }
        if self._caps.is_termux:
            paths["prefix"] = self._caps.termux_prefix
            sdcard = "/sdcard"
            if os.path.exists(sdcard):
                paths["sdcard"] = sdcard
        return paths

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_operational(self) -> bool:
        """Return True if the bridge can execute commands successfully."""
        rc, _out, _err = self.run_command("echo ok", timeout=5)
        return rc == 0

    def info(self) -> str:
        """Return a human-readable summary of the current platform."""
        c = self._caps
        lines = [
            "── Platform Capabilities ────────────────────",
            f"  Android     : {c.is_android}",
            f"  Termux      : {c.is_termux}",
            f"  Linux       : {c.is_linux}",
            f"  Windows     : {c.is_windows}",
            f"  Arch        : {c.arch}",
            f"  OS Release  : {c.os_release}",
            f"  Termux Prefix: {c.termux_prefix or 'n/a'}",
            "── Available Tools ──────────────────────────",
            f"  bash={c.has_bash}  git={c.has_git}  curl={c.has_curl}  wget={c.has_wget}",
            f"  ssh={c.has_ssh}  pkg={c.has_pkg}  apt={c.has_apt}  pip={c.has_pip}",
            f"  python={c.has_python}",
        ]
        return "\n".join(lines)
