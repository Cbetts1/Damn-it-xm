# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Shell
==========
Interactive command-line interface for the AURa AI OS.

Features:
  • Full readline history and tab-completion
  • Pipes output to a pager for long responses
  • Colour prompt with system status
  • Special commands: help, status, ask, plan, analyse, …
  • All unknown input is forwarded to the AI engine

Usage:
  python -m aura shell
  aura shell          (after pip install)
"""

from __future__ import annotations

import os
import readline
import rlcompleter
import sys
import textwrap
from typing import List, Optional, TYPE_CHECKING

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.shell")

# ANSI colours
_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_CYAN    = "\033[96m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_MAGENTA = "\033[95m"
_DIM     = "\033[2m"
_RED     = "\033[91m"

# Shell output formatting constants
_MAX_LINE_WIDTH: int = 120    # lines longer than this are wrapped
_WRAP_WIDTH: int = 110        # target width when wrapping
_BOX_DRAWING_CHARS: str = "─│╔╗╚╝║═◈"  # chars that indicate art/table lines (skip wrapping)

_BANNER = f"""\
{_BOLD}{_CYAN}
  ╔══════════════════════════════════════════════════════╗
  ║   AURa v1.3.0  —  Autonomous Universal Resource     ║
  ║                     Architecture                    ║
  ║   AI OS · Virtual Cloud · Virtual CPU · VServer     ║
  ╚══════════════════════════════════════════════════════╝
{_RESET}{_DIM}  Type 'help' for commands, 'ask <question>' to chat with AI,
  or just type anything to send it to the AI engine.{_RESET}
"""

_SHELL_COMMANDS = [
    "status", "metrics", "cloud", "cpu", "server", "nodes",
    "models", "tasks", "ask", "plan", "analyse", "history",
    "clear_history", "version", "help", "exit", "quit", "clear",
]


class AURaCompleter:
    """Tab-completion for AURa shell commands."""

    def __init__(self, commands: List[str]) -> None:
        self._commands = sorted(commands)

    def complete(self, text: str, state: int):
        if state == 0:
            self._matches = [c for c in self._commands if c.startswith(text)]
        try:
            return self._matches[state]
        except IndexError:
            return None


class AURaShell:
    """
    The AURa interactive shell (REPL).
    Provides a full-featured command environment for operating the AI OS.
    """

    PROMPT = f"{_BOLD}{_CYAN}AURa{_RESET}{_DIM}>{_RESET} "

    def __init__(self, aios: "AIOS") -> None:
        self._aios = aios
        self._logger = get_logger("aura.shell")
        self._setup_readline()

    def _setup_readline(self) -> None:
        try:
            readline.set_completer(AURaCompleter(_SHELL_COMMANDS).complete)
            readline.parse_and_bind("tab: complete")
            hist_file = os.path.join(os.path.expanduser("~"), ".aura", ".shell_history")
            os.makedirs(os.path.dirname(hist_file), exist_ok=True)
            try:
                readline.read_history_file(hist_file)
            except FileNotFoundError:
                pass
            import atexit
            atexit.register(readline.write_history_file, hist_file)
        except Exception:
            pass  # readline not available on all platforms

    def _print(self, text: str) -> None:
        """Print formatted output, wrapping long lines."""
        lines = text.split("\n")
        for line in lines:
            # Don't wrap lines that look like ASCII art / tables
            if len(line) > _MAX_LINE_WIDTH and not any(c in line for c in _BOX_DRAWING_CHARS):
                for chunk in textwrap.wrap(line, _WRAP_WIDTH):
                    print(chunk)
            else:
                print(line)

    def _handle_line(self, line: str) -> bool:
        """
        Process one shell input line.
        Returns True to continue, False to exit.
        """
        line = line.strip()
        if not line:
            return True

        # Split into command + args
        parts = line.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1].split() if len(parts) > 1 else []

        if cmd in ("exit", "quit"):
            print(f"{_DIM}Goodbye.{_RESET}")
            return False

        if cmd == "clear":
            print("\033[2J\033[H", end="")
            return True

        try:
            output = self._aios.dispatch(cmd, rest)
            if output:
                self._print(output)
        except Exception as exc:
            print(f"{_RED}Error: {exc}{_RESET}")
            self._logger.exception("Shell dispatch error")

        return True

    def run(self) -> None:
        """Start the interactive REPL."""
        print(_BANNER)
        # Show a quick status on boot
        try:
            print(self._aios.dispatch("status"))
            print()
        except Exception:
            pass

        while True:
            try:
                line = input(self.PROMPT)
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue
            if not self._handle_line(line):
                break
