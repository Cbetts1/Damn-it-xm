# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Shell Command Executor
============================
Built-in POSIX-style commands for the AURa AI OS shell, plus a
subprocess fallback for everything else.

Features:
  • ``ShellCommandExecutor`` — 20 built-in commands implemented with stdlib
    (cd, ls, cat, pwd, echo, mkdir, rm, cp, mv, touch, head, tail, wc,
    df, free, ps, env, which, date, uname) plus a subprocess passthrough.
  • ``MenuWorkspace`` — numbered menu UI for interactive selection from a
    list of options.

Zero required external dependencies (stdlib only).

Usage::

    executor = ShellCommandExecutor()
    print(executor.execute("ls"))
    print(executor.execute("cat README.md"))
    print(executor.execute("df"))

    menu = MenuWorkspace("Pick an option", ["Start", "Stop", "Quit"])
    choice = menu.show()   # returns "Start" / "Stop" / "Quit" / None
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from aura.utils import get_logger

_logger = get_logger("aura.shell.commands")


# ---------------------------------------------------------------------------
# ShellCommandExecutor
# ---------------------------------------------------------------------------

class ShellCommandExecutor:
    """
    Execute shell commands inside the AURa shell environment.

    Built-in commands are handled without forking a child process; all
    other commands are delegated to :mod:`subprocess`.

    Parameters
    ----------
    cwd:
        Initial working directory.  Defaults to the current directory at
        the time the executor is created.
    env:
        Extra environment variables to inject into subprocess calls.
    timeout:
        Maximum seconds to wait for subprocess commands (``None`` = no limit).
    """

    def __init__(
        self,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = 10.0,
    ) -> None:
        self._cwd: str = cwd or os.getcwd()
        self._env: Dict[str, str] = env or {}
        self._timeout = timeout

        # Map of built-in command names → handler methods
        self._builtins: Dict[str, Any] = {
            "cd":    self._cmd_cd,
            "ls":    self._cmd_ls,
            "cat":   self._cmd_cat,
            "pwd":   self._cmd_pwd,
            "echo":  self._cmd_echo,
            "mkdir": self._cmd_mkdir,
            "rm":    self._cmd_rm,
            "cp":    self._cmd_cp,
            "mv":    self._cmd_mv,
            "touch": self._cmd_touch,
            "head":  self._cmd_head,
            "tail":  self._cmd_tail,
            "wc":    self._cmd_wc,
            "df":    self._cmd_df,
            "free":  self._cmd_free,
            "ps":    self._cmd_ps,
            "env":   self._cmd_env,
            "which": self._cmd_which,
            "date":  self._cmd_date,
            "uname": self._cmd_uname,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cwd(self) -> str:
        """Current working directory of this executor."""
        return self._cwd

    def execute(self, command_line: str) -> str:
        """
        Parse and execute *command_line*.

        Returns the textual output as a string.  An error message is
        returned (not raised) so that the shell REPL can display it.
        """
        command_line = command_line.strip()
        if not command_line:
            return ""

        try:
            parts = shlex.split(command_line)
        except ValueError as exc:
            return f"parse error: {exc}"

        if not parts:
            return ""

        cmd, args = parts[0].lower(), parts[1:]

        if cmd in self._builtins:
            try:
                return self._builtins[cmd](args)
            except Exception as exc:
                return f"{cmd}: {exc}"

        # Subprocess fallback
        return self._run_subprocess(parts)

    def builtin_names(self) -> List[str]:
        """Return the sorted list of built-in command names."""
        return sorted(self._builtins)

    # ------------------------------------------------------------------
    # Built-in implementations
    # ------------------------------------------------------------------

    def _cmd_cd(self, args: List[str]) -> str:
        target = args[0] if args else os.path.expanduser("~")
        target = os.path.expanduser(target)
        if not os.path.isabs(target):
            target = os.path.join(self._cwd, target)
        target = os.path.normpath(target)
        if not os.path.isdir(target):
            return f"cd: {target}: No such file or directory"
        self._cwd = target
        return ""

    def _cmd_ls(self, args: List[str]) -> str:
        show_hidden = "-a" in args or "-la" in args or "-al" in args
        long_fmt = "-l" in args or "-la" in args or "-al" in args
        non_flag = [a for a in args if not a.startswith("-")]
        path = non_flag[0] if non_flag else self._cwd
        if not os.path.isabs(path):
            path = os.path.join(self._cwd, path)
        path = os.path.normpath(path)

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return f"ls: {path}: Permission denied"
        except FileNotFoundError:
            return f"ls: {path}: No such file or directory"

        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]

        if not long_fmt:
            return "  ".join(entries) if entries else ""

        lines = []
        for entry in entries:
            full = os.path.join(path, entry)
            try:
                stat = os.stat(full)
                size = stat.st_size
                mtime = time.strftime("%b %d %H:%M", time.localtime(stat.st_mtime))
                kind = "d" if os.path.isdir(full) else "-"
                lines.append(f"{kind}  {size:>10}  {mtime}  {entry}")
            except OSError:
                lines.append(f"?  {'?':>10}  {'?':>12}  {entry}")
        return "\n".join(lines)

    def _cmd_cat(self, args: List[str]) -> str:
        if not args:
            return "cat: missing file operand"
        results = []
        for filename in args:
            path = filename if os.path.isabs(filename) else os.path.join(self._cwd, filename)
            path = os.path.normpath(path)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    results.append(fh.read())
            except FileNotFoundError:
                results.append(f"cat: {filename}: No such file or directory")
            except PermissionError:
                results.append(f"cat: {filename}: Permission denied")
        return "\n".join(results)

    def _cmd_pwd(self, _args: List[str]) -> str:
        return self._cwd

    def _cmd_echo(self, args: List[str]) -> str:
        return " ".join(args)

    def _cmd_mkdir(self, args: List[str]) -> str:
        if not args:
            return "mkdir: missing operand"
        results = []
        parents = "-p" in args
        targets = [a for a in args if not a.startswith("-")]
        for target in targets:
            path = target if os.path.isabs(target) else os.path.join(self._cwd, target)
            path = os.path.normpath(path)
            try:
                if parents:
                    os.makedirs(path, exist_ok=True)
                else:
                    os.mkdir(path)
            except FileExistsError:
                results.append(f"mkdir: {target}: File exists")
            except PermissionError:
                results.append(f"mkdir: {target}: Permission denied")
        return "\n".join(results)

    def _cmd_rm(self, args: List[str]) -> str:
        if not args:
            return "rm: missing operand"
        recursive = "-r" in args or "-rf" in args or "-fr" in args
        targets = [a for a in args if not a.startswith("-")]
        results = []
        for target in targets:
            path = target if os.path.isabs(target) else os.path.join(self._cwd, target)
            path = os.path.normpath(path)
            try:
                if os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        results.append(f"rm: {target}: is a directory")
                elif os.path.isfile(path):
                    os.remove(path)
                else:
                    results.append(f"rm: {target}: No such file or directory")
            except PermissionError:
                results.append(f"rm: {target}: Permission denied")
        return "\n".join(results)

    def _cmd_cp(self, args: List[str]) -> str:
        non_flags = [a for a in args if not a.startswith("-")]
        if len(non_flags) < 2:
            return "cp: missing destination"
        src_rel, dst_rel = non_flags[0], non_flags[-1]
        src = src_rel if os.path.isabs(src_rel) else os.path.join(self._cwd, src_rel)
        dst = dst_rel if os.path.isabs(dst_rel) else os.path.join(self._cwd, dst_rel)
        src, dst = os.path.normpath(src), os.path.normpath(dst)
        try:
            shutil.copy2(src, dst)
        except FileNotFoundError:
            return f"cp: {src_rel}: No such file or directory"
        except PermissionError:
            return f"cp: Permission denied"
        return ""

    def _cmd_mv(self, args: List[str]) -> str:
        non_flags = [a for a in args if not a.startswith("-")]
        if len(non_flags) < 2:
            return "mv: missing destination"
        src_rel, dst_rel = non_flags[0], non_flags[-1]
        src = src_rel if os.path.isabs(src_rel) else os.path.join(self._cwd, src_rel)
        dst = dst_rel if os.path.isabs(dst_rel) else os.path.join(self._cwd, dst_rel)
        src, dst = os.path.normpath(src), os.path.normpath(dst)
        try:
            shutil.move(src, dst)
        except FileNotFoundError:
            return f"mv: {src_rel}: No such file or directory"
        except PermissionError:
            return f"mv: Permission denied"
        return ""

    def _cmd_touch(self, args: List[str]) -> str:
        if not args:
            return "touch: missing file operand"
        results = []
        for filename in args:
            path = filename if os.path.isabs(filename) else os.path.join(self._cwd, filename)
            path = os.path.normpath(path)
            try:
                with open(path, "a", encoding="utf-8"):
                    os.utime(path, None)
            except PermissionError:
                results.append(f"touch: {filename}: Permission denied")
        return "\n".join(results)

    def _cmd_head(self, args: List[str]) -> str:
        n = 10
        non_flags: List[str] = []
        i = 0
        while i < len(args):
            if args[i] in ("-n",) and i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                non_flags.append(args[i])
                i += 1
        if not non_flags:
            return "head: missing file operand"
        path = non_flags[0] if os.path.isabs(non_flags[0]) else os.path.join(self._cwd, non_flags[0])
        try:
            with open(os.path.normpath(path), "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            return "".join(lines[:n]).rstrip("\n")
        except FileNotFoundError:
            return f"head: {non_flags[0]}: No such file or directory"

    def _cmd_tail(self, args: List[str]) -> str:
        n = 10
        non_flags: List[str] = []
        i = 0
        while i < len(args):
            if args[i] in ("-n",) and i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                non_flags.append(args[i])
                i += 1
        if not non_flags:
            return "tail: missing file operand"
        path = non_flags[0] if os.path.isabs(non_flags[0]) else os.path.join(self._cwd, non_flags[0])
        try:
            with open(os.path.normpath(path), "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            return "".join(lines[-n:]).rstrip("\n")
        except FileNotFoundError:
            return f"tail: {non_flags[0]}: No such file or directory"

    def _cmd_wc(self, args: List[str]) -> str:
        if not args:
            return "wc: missing file operand"
        non_flags = [a for a in args if not a.startswith("-")]
        if not non_flags:
            return "wc: missing file operand"
        path = non_flags[0] if os.path.isabs(non_flags[0]) else os.path.join(self._cwd, non_flags[0])
        try:
            with open(os.path.normpath(path), "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            lines = content.count("\n")
            words = len(content.split())
            chars = len(content)
            return f"{lines:>7} {words:>7} {chars:>7} {non_flags[0]}"
        except FileNotFoundError:
            return f"wc: {non_flags[0]}: No such file or directory"

    def _cmd_df(self, _args: List[str]) -> str:
        try:
            total, used, free = shutil.disk_usage(self._cwd)
            header = f"{'Filesystem':<20} {'Size':>10} {'Used':>10} {'Avail':>10} {'Use%':>5}"
            row = (
                f"{'(virtual)':.<20} "
                f"{self._fmt_size(total):>10} "
                f"{self._fmt_size(used):>10} "
                f"{self._fmt_size(free):>10} "
                f"{(used / total * 100):.1f}%"
            )
            return header + "\n" + row
        except OSError as exc:
            return f"df: {exc}"

    def _cmd_free(self, _args: List[str]) -> str:
        try:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            mem_line = f"{'Mem:':<10} {'limit':>10} {'soft':>15} {'hard':>15}\n"
            mem_line += f"{'':10} {'N/A':>10} {soft:>15} {hard:>15}"
            return mem_line
        except (ImportError, AttributeError):
            # Windows or stripped Python
            return "free: memory information unavailable on this platform"

    def _cmd_ps(self, _args: List[str]) -> str:
        pid = os.getpid()
        ppid = os.getppid() if hasattr(os, "getppid") else "N/A"
        return (
            f"{'PID':>7} {'PPID':>7} {'NAME'}\n"
            f"{pid:>7} {str(ppid):>7} python"
        )

    def _cmd_env(self, args: List[str]) -> str:
        env = {**os.environ, **self._env}
        lines = [f"{k}={v}" for k, v in sorted(env.items())]
        return "\n".join(lines)

    def _cmd_which(self, args: List[str]) -> str:
        if not args:
            return "which: missing argument"
        results = []
        for name in args:
            path = shutil.which(name)
            results.append(path if path else f"{name}: not found")
        return "\n".join(results)

    def _cmd_date(self, _args: List[str]) -> str:
        return time.strftime("%a %b %d %H:%M:%S %Z %Y")

    def _cmd_uname(self, args: List[str]) -> str:
        if "-a" in args:
            return " ".join([
                platform.system(),
                platform.node(),
                platform.release(),
                platform.version(),
                platform.machine(),
            ])
        return platform.system()

    # ------------------------------------------------------------------
    # Subprocess fallback
    # ------------------------------------------------------------------

    def _run_subprocess(self, parts: List[str]) -> str:
        merged_env = {**os.environ, **self._env}
        try:
            proc = subprocess.run(
                parts,
                cwd=self._cwd,
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self._timeout,
            )
            return proc.stdout.rstrip("\n") if proc.stdout else ""
        except FileNotFoundError:
            return f"{parts[0]}: command not found"
        except subprocess.TimeoutExpired:
            return f"{parts[0]}: command timed out"
        except PermissionError:
            return f"{parts[0]}: Permission denied"
        except OSError as exc:
            return str(exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ("B", "K", "M", "G", "T"):
            if n < 1024:
                return f"{n:.0f}{unit}"
            n //= 1024
        return f"{n}P"


# ---------------------------------------------------------------------------
# MenuWorkspace
# ---------------------------------------------------------------------------

class MenuWorkspace:
    """
    Numbered menu UI for interactive option selection in the AURa shell.

    Parameters
    ----------
    title:
        Heading shown above the menu.
    options:
        List of option strings to present.
    prompt:
        Input prompt text (default ``"Select> "``).

    Example::

        menu = MenuWorkspace("What would you like to do?", ["Start", "Stop", "Quit"])
        choice = menu.show()
        # User types "1" → returns "Start"
    """

    def __init__(
        self,
        title: str,
        options: List[str],
        prompt: str = "Select> ",
    ) -> None:
        if not options:
            raise ValueError("options must not be empty")
        self._title = title
        self._options = options
        self._prompt = prompt

    def render(self) -> str:
        """Return the menu as a formatted string (without prompting for input)."""
        lines = [f"\n{self._title}", "─" * min(len(self._title) + 4, 60)]
        for i, opt in enumerate(self._options, start=1):
            lines.append(f"  [{i}] {opt}")
        lines.append("")
        return "\n".join(lines)

    def show(self) -> Optional[str]:
        """
        Print the menu and block for user input.

        Returns the selected option string, or ``None`` if the input was
        invalid / empty.
        """
        print(self.render(), end="")
        try:
            raw = input(self._prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw:
            return None
        try:
            idx = int(raw)
        except ValueError:
            # Allow the user to type the option text directly
            lower = raw.lower()
            for opt in self._options:
                if opt.lower() == lower:
                    return opt
            return None
        if 1 <= idx <= len(self._options):
            return self._options[idx - 1]
        return None
