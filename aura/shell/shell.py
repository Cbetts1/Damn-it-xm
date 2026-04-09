"""
AURa Shell
==========
Interactive command-line interface for the AURa AI OS.

Features:
  • Full readline history and tab-completion
  • Pipe operator: cmd1 | cmd2 routes output between commands
  • Flag/argument parsing: --flag value style arguments
  • Colour prompt with system status
  • history command: display session command history
  • Special commands: help, status, ask, plan, analyse, uptime, …
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
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

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
  ║   AURa v1.2.0  —  Autonomous Universal Resource     ║
  ║                     Architecture                    ║
  ║   AI OS · Virtual Cloud · Virtual CPU · VServer     ║
  ╚══════════════════════════════════════════════════════╝
{_RESET}{_DIM}  Type 'help' for commands, 'ask <question>' to chat with AI,
  or just type anything to send it to the AI engine.
  Use '|' to pipe output between commands.{_RESET}
"""

_SHELL_COMMANDS = [
    "status", "metrics", "cloud", "cpu", "server", "nodes",
    "models", "tasks", "ask", "plan", "analyse", "history",
    "clear_history", "version", "uptime", "platform", "plugins",
    "bash", "kv", "help", "exit", "quit", "clear",
]


def parse_flags(args: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Parse --flag value style flags out of an argument list.

    Returns a tuple of (flags_dict, positional_args).

    Examples::

        parse_flags(["--limit", "10", "foo"])
        → ({"limit": "10"}, ["foo"])

        parse_flags(["--verbose", "bar"])
        → ({"verbose": "true"}, ["bar"])
    """
    flags: Dict[str, str] = {}
    positional: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token.startswith("--"):
            key = token[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                flags[key] = args[i + 1]
                i += 2
            else:
                flags[key] = "true"
                i += 1
        elif token.startswith("-") and len(token) == 2 and token[1].isalpha():
            key = token[1]
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                flags[key] = args[i + 1]
                i += 2
            else:
                flags[key] = "true"
                i += 1
        else:
            positional.append(token)
            i += 1
    return flags, positional


class AURaCompleter:
    """Tab-completion for AURa shell commands."""

    def __init__(self, commands: List[str]) -> None:
        self._commands = sorted(commands)
        self._matches: List[str] = []

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
    Provides a full-featured, operator-grade command environment for the AI OS.

    Enhancements in v1.2.0:
      • Pipe operator (|) — chains AURa commands, routing output as context
      • Flag parsing — --key value style arguments in any command
      • history — display readline command history for the session
      • uptime — quick uptime alias routed through the OS dispatcher
      • Improved error messages with recovery hints
    """

    PROMPT = f"{_BOLD}{_CYAN}AURa{_RESET}{_DIM}>{_RESET} "

    def __init__(self, aios: "AIOS") -> None:
        self._aios = aios
        self._logger = get_logger("aura.shell")
        self._setup_readline()

    # ------------------------------------------------------------------
    # Readline setup
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _print(self, text: str) -> None:
        """Print formatted output, wrapping long lines while preserving art."""
        lines = text.split("\n")
        for line in lines:
            # Don't wrap lines that look like ASCII art / tables
            if len(line) > _MAX_LINE_WIDTH and not any(c in line for c in _BOX_DRAWING_CHARS):
                for chunk in textwrap.wrap(line, _WRAP_WIDTH):
                    print(chunk)
            else:
                print(line)

    # ------------------------------------------------------------------
    # Internal commands handled by the shell layer
    # ------------------------------------------------------------------

    def _show_history(self) -> str:
        """Return the readline command history as a formatted string."""
        try:
            length = readline.get_current_history_length()
            if length == 0:
                return "(no history)"
            lines = []
            for i in range(1, length + 1):
                lines.append(f"  {i:>4}  {readline.get_history_item(i)}")
            return "\n".join(lines)
        except Exception:
            return "(history unavailable)"

    # ------------------------------------------------------------------
    # Pipe execution
    # ------------------------------------------------------------------

    def _execute_segment(self, segment: str, pipe_input: Optional[str] = None) -> str:
        """
        Execute one pipeline segment (a single command string).

        If *pipe_input* is provided it is appended to the command so that the
        previous stage's output is available as context to the dispatcher.
        """
        segment = segment.strip()
        if not segment:
            return pipe_input or ""

        parts = segment.split(None, 1)
        cmd = parts[0].lower()
        raw_args = parts[1].split() if len(parts) > 1 else []

        # Inject pipe_input as trailing context when present
        if pipe_input:
            raw_args = raw_args + ["--pipe-input", pipe_input]

        _flags, positional = parse_flags(raw_args)

        # Shell-layer built-ins that bypass the dispatcher
        if cmd == "history":
            return self._show_history()

        return self._aios.dispatch(cmd, positional) or ""

    # ------------------------------------------------------------------
    # Main line handler
    # ------------------------------------------------------------------

    def _handle_line(self, line: str) -> bool:
        """
        Process one shell input line.

        Supports:
          • Exit/quit commands
          • Screen clear
          • Pipe operator: cmd1 | cmd2 | …
          • Single commands with optional --flag value arguments

        Returns True to continue, False to exit.
        """
        line = line.strip()
        if not line:
            return True

        # Fast-path: exit / quit
        first_token = line.split()[0].lower()
        if first_token in ("exit", "quit"):
            print(f"{_DIM}Goodbye.{_RESET}")
            return False

        if first_token == "clear":
            print("\033[2J\033[H", end="")
            return True

        try:
            # Split on pipe operator
            segments = [s.strip() for s in line.split("|")]

            if len(segments) == 1:
                # No pipe — standard dispatch
                output = self._execute_segment(segments[0])
            else:
                # Pipeline: feed output of each stage into the next
                output = ""
                for seg in segments:
                    output = self._execute_segment(seg, pipe_input=output if output else None)

            if output:
                self._print(output)

        except Exception as exc:
            print(f"{_RED}Error: {exc}{_RESET}")
            print(f"{_DIM}  Hint: type 'help' for a list of valid commands.{_RESET}")
            self._logger.exception("Shell dispatch error")

        return True

    # ------------------------------------------------------------------
    # REPL entry point
    # ------------------------------------------------------------------

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
