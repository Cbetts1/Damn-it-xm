# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Android / Cross-platform Bridge
=====================================
Platform detection and cross-platform subprocess execution for the AURa AI OS.

Features:
  • ``detect_capabilities()`` — stdlib-only environment probe that reports
    the host platform, available shells, Python version, key tool presence,
    and Termux / Android detection.
  • ``AndroidBridge`` — unified subprocess runner that transparently handles
    Linux, Windows, macOS, and Termux/Android differences.

Zero required external dependencies (stdlib only).

Usage::

    caps = detect_capabilities()
    print(caps["platform"])          # "linux" / "windows" / "darwin" / "android"

    bridge = AndroidBridge()
    result = bridge.run(["echo", "hello"])
    print(result.stdout)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aura.utils import get_logger

_logger = get_logger("aura.adapters")

# ---------------------------------------------------------------------------
# Capability detection
# ---------------------------------------------------------------------------

def detect_capabilities() -> Dict[str, object]:
    """
    Probe the current runtime environment using only the stdlib.

    Returns a dict with the following keys:

    ``platform``
        Normalised OS name: ``"android"``, ``"linux"``, ``"darwin"``,
        ``"windows"``, or ``"unknown"``.

    ``is_termux``
        ``True`` when running inside Termux on Android.

    ``python_version``
        The full Python version string (e.g. ``"3.11.4"``).

    ``architecture``
        Machine architecture as reported by :func:`platform.machine`.

    ``shells``
        Dict mapping shell names to their resolved paths (or ``None``).
        Checked: ``sh``, ``bash``, ``zsh``, ``fish``, ``cmd``, ``powershell``.

    ``tools``
        Dict mapping useful POSIX/system tool names to ``True``/``False``
        depending on whether they are discoverable on ``PATH``.
        Checked: ``ls``, ``cat``, ``grep``, ``find``, ``curl``, ``wget``,
        ``git``, ``python3``, ``pip3``, ``adb``.

    ``env_vars``
        A filtered snapshot of relevant environment variables
        (``HOME``, ``PATH``, ``TMPDIR``, ``PREFIX``, ``ANDROID_ROOT``,
        ``TERMUX_VERSION``).

    ``cpu_count``
        Number of logical CPUs (may be ``None``).

    ``path_sep``
        The OS path separator.
    """
    is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux")
    is_android = is_termux or os.path.isdir("/system/app") or bool(os.environ.get("ANDROID_ROOT"))

    raw_platform = sys.platform
    if is_android:
        norm_platform = "android"
    elif raw_platform.startswith("linux"):
        norm_platform = "linux"
    elif raw_platform == "darwin":
        norm_platform = "darwin"
    elif raw_platform == "win32":
        norm_platform = "windows"
    else:
        norm_platform = "unknown"

    shell_names = ["sh", "bash", "zsh", "fish", "cmd", "powershell"]
    shells: Dict[str, Optional[str]] = {s: shutil.which(s) for s in shell_names}

    tool_names = ["ls", "cat", "grep", "find", "curl", "wget", "git", "python3", "pip3", "adb"]
    tools: Dict[str, bool] = {t: shutil.which(t) is not None for t in tool_names}

    env_keys = ["HOME", "PATH", "TMPDIR", "PREFIX", "ANDROID_ROOT", "TERMUX_VERSION"]
    env_vars = {k: os.environ.get(k) for k in env_keys}

    caps = {
        "platform": norm_platform,
        "is_termux": is_termux,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "shells": shells,
        "tools": tools,
        "env_vars": env_vars,
        "cpu_count": os.cpu_count(),
        "path_sep": os.sep,
    }

    _logger.debug("Capabilities detected: platform=%s is_termux=%s", norm_platform, is_termux)
    return caps


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Result of a subprocess command executed by :class:`AndroidBridge`."""
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def __str__(self) -> str:  # pragma: no cover
        status = "OK" if self.success else f"FAIL({self.returncode})"
        return f"RunResult[{status}] {self.command!r}"


# ---------------------------------------------------------------------------
# AndroidBridge
# ---------------------------------------------------------------------------

class AndroidBridge:
    """
    Cross-platform subprocess runner for AURa.

    Transparently handles:
      - Linux / macOS:  standard ``/bin/sh`` invocation
      - Windows:        ``cmd.exe`` / PowerShell detection + ``shell=True``
      - Termux/Android: ``$PREFIX/bin`` path injection + Termux API helpers

    Parameters
    ----------
    capabilities:
        Optional pre-computed capabilities dict from :func:`detect_capabilities`.
        If omitted, capabilities are probed on first use.
    timeout:
        Default timeout in seconds for subprocess calls (``None`` = no limit).
    """

    def __init__(
        self,
        capabilities: Optional[Dict[str, object]] = None,
        timeout: Optional[float] = 30.0,
    ) -> None:
        self._caps = capabilities or detect_capabilities()
        self._timeout = timeout
        self._platform: str = self._caps["platform"]  # type: ignore[assignment]
        _logger.debug("AndroidBridge initialised for platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        command: List[str],
        *,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        capture: bool = True,
    ) -> RunResult:
        """
        Execute *command* and return a :class:`RunResult`.

        Parameters
        ----------
        command:
            Command and arguments as a list, e.g. ``["ls", "-la"]``.
        cwd:
            Working directory; defaults to the current directory.
        env:
            Additional environment variables to inject.  These are merged
            on top of the current environment.
        timeout:
            Per-call timeout in seconds; falls back to the instance default.
        capture:
            When ``True`` (default) stdout/stderr are captured and returned
            in :class:`RunResult`.  When ``False`` the subprocess inherits
            the parent's streams (useful for interactive commands).
        """
        if not command:
            raise ValueError("command must be a non-empty list")

        merged_env = self._build_env(env)
        effective_timeout = timeout if timeout is not None else self._timeout
        use_shell = self._platform == "windows"

        kwargs: dict = {
            "cwd": cwd,
            "env": merged_env,
            "shell": use_shell,
        }
        if capture:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.PIPE

        timed_out = False
        try:
            proc = subprocess.run(
                command if not use_shell else " ".join(command),
                timeout=effective_timeout,
                text=True,
                **kwargs,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            stdout = ""
            stderr = f"Command timed out after {effective_timeout}s"
            returncode = -1
        except FileNotFoundError:
            stdout = ""
            stderr = f"Command not found: {command[0]!r}"
            returncode = 127
        except OSError as exc:
            stdout = ""
            stderr = str(exc)
            returncode = 1

        result = RunResult(
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
        )
        _logger.debug(
            "run %r → returncode=%d timed_out=%s",
            command,
            returncode,
            timed_out,
        )
        return result

    def run_shell(self, command_str: str, **kwargs) -> RunResult:
        """
        Convenience wrapper: run a shell string using the platform shell.

        On Linux/macOS/Android this invokes ``sh -c <command_str>``.
        On Windows this invokes ``cmd /C <command_str>``.
        """
        if self._platform == "windows":
            shell_cmd = ["cmd", "/C", command_str]
        else:
            sh = self._caps.get("shells", {}).get("sh") or "sh"  # type: ignore[arg-type]
            shell_cmd = [sh, "-c", command_str]
        return self.run(shell_cmd, **kwargs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self, extra: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Build the subprocess environment, injecting Termux PATH if needed."""
        merged = dict(os.environ)
        if self._caps.get("is_termux"):
            prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
            termux_bin = os.path.join(prefix, "bin")
            path = merged.get("PATH", "")
            if termux_bin not in path.split(os.pathsep):
                merged["PATH"] = termux_bin + os.pathsep + path
        if extra:
            merged.update(extra)
        return merged
