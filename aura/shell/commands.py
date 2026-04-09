"""
AURa Shell Command Executor & Menu Workspace
============================================
Provides a built-in shell command emulator (no external dependencies) and
a text-based interactive menu for the AURa AI OS.

Classes:
  • ShellCommandExecutor — emulates common POSIX shell commands in-process
  • MenuWorkspace        — ASCII menu wrapper around the AI OS
"""

from __future__ import annotations

import datetime
import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import time
from typing import List, Optional, Tuple, TYPE_CHECKING

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.shell.commands")

# ANSI codes used by MenuWorkspace
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_DIM    = "\033[2m"


# ---------------------------------------------------------------------------
# ShellCommandExecutor
# ---------------------------------------------------------------------------

class ShellCommandExecutor:
    """
    In-process emulator of common POSIX shell commands.

    Built-in commands are handled natively (no subprocess).  Any unknown
    command is forwarded to the system shell with a 30-second timeout.
    """

    _MAX_HISTORY = 100

    def __init__(self, cwd: Optional[str] = None) -> None:
        self._cwd: str = cwd or os.path.expanduser("~")
        if not os.path.isdir(self._cwd):
            self._cwd = os.getcwd()
        self._env: dict = dict(os.environ)
        self._history: List[str] = []
        self._start_time: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def cwd(self) -> str:
        return self._cwd

    def get_history(self) -> List[str]:
        return list(self._history)

    def execute(self, line: str) -> str:
        """
        Execute *line* as a shell command and return the output string.

        Built-in commands are handled in-process; everything else is
        delegated to the system shell.
        """
        line = line.strip()
        if not line:
            return ""

        # Record in history
        self._history.append(line)
        if len(self._history) > self._MAX_HISTORY:
            self._history = self._history[-self._MAX_HISTORY:]

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            return f"parse error: {exc}"

        if not parts:
            return ""

        cmd, *rest = parts

        # Dispatch to built-in handlers
        dispatch = {
            "pwd":    self._cmd_pwd,
            "cd":     self._cmd_cd,
            "ls":     self._cmd_ls,
            "mkdir":  self._cmd_mkdir,
            "rm":     self._cmd_rm,
            "cp":     self._cmd_cp,
            "mv":     self._cmd_mv,
            "cat":    self._cmd_cat,
            "echo":   self._cmd_echo,
            "env":    self._cmd_env,
            "export": self._cmd_export,
            "which":  self._cmd_which,
            "uname":  self._cmd_uname,
            "whoami": self._cmd_whoami,
            "date":   self._cmd_date,
            "uptime": self._cmd_uptime,
            "df":     self._cmd_df,
            "free":   self._cmd_free,
            "ps":     self._cmd_ps,
            "history":self._cmd_history,
            "clear":  self._cmd_clear,
        }

        if cmd in dispatch:
            try:
                return dispatch[cmd](rest)
            except Exception as exc:
                _logger.debug("Built-in %s error: %s", cmd, exc)
                return f"{cmd}: {exc}"

        # Fallback — subprocess
        return self._run_external(line)

    # ------------------------------------------------------------------
    # Built-in command implementations
    # ------------------------------------------------------------------

    def _cmd_pwd(self, args: List[str]) -> str:
        return self._cwd

    def _cmd_cd(self, args: List[str]) -> str:
        target = args[0] if args else os.path.expanduser("~")
        # Handle ~ expansion
        target = os.path.expanduser(target)
        if not os.path.isabs(target):
            target = os.path.join(self._cwd, target)
        target = os.path.normpath(target)
        if not os.path.isdir(target):
            return f"cd: {target}: No such file or directory"
        self._cwd = target
        return ""

    def _cmd_ls(self, args: List[str]) -> str:
        show_long = False
        show_all = False
        paths: List[str] = []

        for a in args:
            if a.startswith("-"):
                if "l" in a:
                    show_long = True
                if "a" in a:
                    show_all = True
            else:
                paths.append(a)

        target = paths[0] if paths else self._cwd
        if not os.path.isabs(target):
            target = os.path.join(self._cwd, target)
        target = os.path.normpath(target)

        try:
            entries = os.listdir(target)
        except PermissionError:
            return f"ls: {target}: Permission denied"
        except FileNotFoundError:
            return f"ls: {target}: No such file or directory"

        if not show_all:
            entries = [e for e in entries if not e.startswith(".")]
        entries.sort()

        if not show_long:
            return "  ".join(entries)

        lines = []
        for name in entries:
            full = os.path.join(target, name)
            try:
                st = os.stat(full)
                mode = stat.filemode(st.st_mode)
                size = st.st_size
                mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"{mode}  {size:>10}  {mtime}  {name}")
            except OSError:
                lines.append(f"??????????  {'?':>10}  ????-??-?? ??:??  {name}")
        return "\n".join(lines)

    def _cmd_mkdir(self, args: List[str]) -> str:
        parents = "-p" in args
        dirs = [a for a in args if not a.startswith("-")]
        if not dirs:
            return "mkdir: missing operand"
        for d in dirs:
            if not os.path.isabs(d):
                d = os.path.join(self._cwd, d)
            try:
                if parents:
                    os.makedirs(d, exist_ok=True)
                else:
                    os.mkdir(d)
            except FileExistsError:
                if not parents:
                    return f"mkdir: {d}: File exists"
            except Exception as exc:
                return f"mkdir: {exc}"
        return ""

    def _cmd_rm(self, args: List[str]) -> str:
        recursive = "-r" in args or "-rf" in args or "-fr" in args
        force = "-f" in args or "-rf" in args or "-fr" in args
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            return "rm: missing operand"
        for p in paths:
            if not os.path.isabs(p):
                p = os.path.join(self._cwd, p)
            p = os.path.normpath(p)
            try:
                if os.path.isdir(p):
                    if recursive:
                        shutil.rmtree(p)
                    else:
                        return f"rm: {p}: is a directory (use -r)"
                elif os.path.exists(p):
                    os.remove(p)
                elif not force:
                    return f"rm: {p}: No such file or directory"
            except Exception as exc:
                return f"rm: {exc}"
        return ""

    def _cmd_cp(self, args: List[str]) -> str:
        non_flag = [a for a in args if not a.startswith("-")]
        if len(non_flag) < 2:
            return "cp: missing destination"
        src, dst = non_flag[0], non_flag[-1]
        src = os.path.normpath(src if os.path.isabs(src) else os.path.join(self._cwd, src))
        dst = os.path.normpath(dst if os.path.isabs(dst) else os.path.join(self._cwd, dst))
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        except Exception as exc:
            return f"cp: {exc}"
        return ""

    def _cmd_mv(self, args: List[str]) -> str:
        non_flag = [a for a in args if not a.startswith("-")]
        if len(non_flag) < 2:
            return "mv: missing destination"
        src, dst = non_flag[0], non_flag[-1]
        src = os.path.normpath(src if os.path.isabs(src) else os.path.join(self._cwd, src))
        dst = os.path.normpath(dst if os.path.isabs(dst) else os.path.join(self._cwd, dst))
        try:
            shutil.move(src, dst)
        except Exception as exc:
            return f"mv: {exc}"
        return ""

    def _cmd_cat(self, args: List[str]) -> str:
        if not args:
            return "cat: missing file operand"
        parts = []
        for fname in args:
            if not os.path.isabs(fname):
                fname = os.path.join(self._cwd, fname)
            try:
                with open(fname, "r", errors="replace") as fh:
                    parts.append(fh.read())
            except FileNotFoundError:
                parts.append(f"cat: {fname}: No such file or directory")
            except PermissionError:
                parts.append(f"cat: {fname}: Permission denied")
        return "\n".join(parts)

    def _cmd_echo(self, args: List[str]) -> str:
        # Expand env variables inline ($VAR or ${VAR})
        text = " ".join(args)
        import re
        def _expand(m):
            return self._env.get(m.group(1) or m.group(2), "")
        text = re.sub(r'\$\{(\w+)\}|\$(\w+)', _expand, text)
        return text

    def _cmd_env(self, args: List[str]) -> str:
        return "\n".join(f"{k}={v}" for k, v in sorted(self._env.items()))

    def _cmd_export(self, args: List[str]) -> str:
        for a in args:
            if "=" in a:
                key, _, val = a.partition("=")
                self._env[key.strip()] = val.strip()
            else:
                # export VAR — mark for export (already in env dict)
                pass
        return ""

    def _cmd_which(self, args: List[str]) -> str:
        if not args:
            return "which: missing argument"
        results = []
        for cmd in args:
            path = shutil.which(cmd)
            results.append(path if path else f"{cmd} not found")
        return "\n".join(results)

    def _cmd_uname(self, args: List[str]) -> str:
        show_all = "-a" in args
        if show_all:
            return " ".join([
                platform.system(),
                platform.node(),
                platform.release(),
                platform.version(),
                platform.machine(),
            ])
        return platform.system()

    def _cmd_whoami(self, args: List[str]) -> str:
        try:
            import pwd
            return pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

    def _cmd_date(self, args: List[str]) -> str:
        return datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y")

    def _cmd_uptime(self, args: List[str]) -> str:
        elapsed = time.monotonic() - self._start_time
        h, rem = divmod(int(elapsed), 3600)
        m, s = divmod(rem, 60)
        return f"up {h:02d}:{m:02d}:{s:02d}  (shell session)"

    def _cmd_df(self, args: List[str]) -> str:
        human = "-h" in args
        try:
            usage = shutil.disk_usage(self._cwd)
            total = usage.total
            used  = usage.used
            free  = usage.free
            if human:
                def _h(n):
                    for unit in ("B", "K", "M", "G", "T"):
                        if n < 1024:
                            return f"{n:.0f}{unit}"
                        n /= 1024
                    return f"{n:.0f}P"
                return (
                    f"Filesystem      Size  Used Avail Use%\n"
                    f"{self._cwd:<15} {_h(total):>5} {_h(used):>5} {_h(free):>5} "
                    f"{used/total*100:.0f}%"
                )
            return (
                f"Filesystem      1K-blocks    Used Available Use%\n"
                f"{self._cwd:<15} {total//1024:>10} {used//1024:>7} {free//1024:>9} "
                f"{used/total*100:.0f}%"
            )
        except Exception as exc:
            return f"df: {exc}"

    def _cmd_free(self, args: List[str]) -> str:
        human = "-h" in args

        def _h(n):
            if not human:
                return str(n // 1024)
            for unit in ("B", "K", "M", "G"):
                if n < 1024:
                    return f"{n:.0f}{unit}"
                n /= 1024
            return f"{n:.0f}T"

        try:
            meminfo: dict = {}
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo") as fh:
                    for line in fh:
                        k, _, v = line.partition(":")
                        meminfo[k.strip()] = int(v.split()[0]) * 1024
                total = meminfo.get("MemTotal", 0)
                free  = meminfo.get("MemFree", 0)
                avail = meminfo.get("MemAvailable", free)
                used  = total - free
                header = "       " + ("   total      used      free  available" if human else
                                      "         total       used       free     available")
                return f"{header}\nMem:  {_h(total):>9} {_h(used):>9} {_h(free):>9} {_h(avail):>9}"
            else:
                # Fallback — use virtual dummy values
                return "free: /proc/meminfo not available on this platform"
        except Exception as exc:
            return f"free: {exc}"

    def _cmd_ps(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                ["ps"] + args, capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or result.stderr.strip()
        except FileNotFoundError:
            return "ps: command not available"
        except Exception as exc:
            return f"ps: {exc}"

    def _cmd_history(self, args: List[str]) -> str:
        lines = []
        for i, entry in enumerate(self._history, 1):
            lines.append(f"  {i:>4}  {entry}")
        return "\n".join(lines) if lines else "(empty)"

    def _cmd_clear(self, args: List[str]) -> str:
        return "\033[2J\033[H"

    # ------------------------------------------------------------------
    # External command fallback
    # ------------------------------------------------------------------

    def _run_external(self, line: str) -> str:
        try:
            result = subprocess.run(
                line,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self._cwd,
                env=self._env,
            )
            out = result.stdout
            err = result.stderr
            if result.returncode != 0 and not out:
                return err.strip() if err else f"Command exited with code {result.returncode}"
            return (out + err).rstrip()
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as exc:
            return f"Error: {exc}"


# ---------------------------------------------------------------------------
# MenuWorkspace
# ---------------------------------------------------------------------------

_MENU_TEXT = f"""\
{_BOLD}{_CYAN}
  ╔══════════════════════════════════════════════════════════╗
  ║            AURa AI OS  —  Main Menu                    ║
  ╚══════════════════════════════════════════════════════════╝
{_RESET}
  {_BOLD}1.{_RESET}  Shell            — Enter interactive bash shell mode
  {_BOLD}2.{_RESET}  AI Chat          — Chat with the AI engine
  {_BOLD}3.{_RESET}  System Status    — View system health
  {_BOLD}4.{_RESET}  Cloud Manager    — Cloud nodes and volumes
  {_BOLD}5.{_RESET}  CPU Monitor      — Task queue and metrics
  {_BOLD}6.{_RESET}  Server Dashboard — API server status
  {_BOLD}7.{_RESET}  Storage Manager  — Files and persistence
  {_BOLD}8.{_RESET}  Android Bridge   — Platform capabilities
  {_BOLD}9.{_RESET}  Plugin Manager   — Installed plugins
  {_BOLD}0.{_RESET}  Exit AURa

"""


class MenuWorkspace:
    """
    Text-based interactive menu for the AURa AI OS.

    Wraps the AIOS dispatch API behind a numbered-option menu that can be
    driven from a standard terminal.
    """

    def __init__(self, aios: "AIOS") -> None:
        self._aios = aios
        self._executor = ShellCommandExecutor()

    def render_menu(self) -> str:
        """Return the ASCII menu string."""
        return _MENU_TEXT

    def handle_choice(self, choice: str) -> Tuple[str, bool]:
        """
        Process a menu selection.

        Returns ``(output_text, should_exit)``.
        """
        choice = choice.strip()

        if choice == "0":
            return ("Goodbye from AURa!", True)

        elif choice == "1":
            # Inline mini-shell loop is not suitable from handle_choice;
            # return guidance text instead.
            return (
                "Shell mode: type commands prefixed with '!' in the main shell,\n"
                "or use 'bash <cmd>' to run a single command.",
                False,
            )

        elif choice == "2":
            try:
                prompt = input(f"  {_CYAN}You>{_RESET} ").strip()
                out = self._aios.dispatch("ask", [prompt])
            except (EOFError, KeyboardInterrupt):
                out = "(cancelled)"
            return (out, False)

        elif choice == "3":
            return (self._aios.dispatch("status"), False)

        elif choice == "4":
            return (self._aios.dispatch("nodes"), False)

        elif choice == "5":
            return (self._aios.dispatch("cpu"), False)

        elif choice == "6":
            return (self._aios.dispatch("server"), False)

        elif choice == "7":
            try:
                p = self._aios.persistence  # type: ignore[attr-defined]
                m = p.metrics()
                out = (
                    f"Storage Manager\n"
                    f"  Namespaces : {m['namespace_count']}\n"
                    f"  Total keys : {m['total_keys']}\n"
                    f"  Storage    : {m['storage_bytes']} bytes"
                )
            except Exception:
                out = self._aios.dispatch("status")
            return (out, False)

        elif choice == "8":
            try:
                bridge = self._aios.android_bridge  # type: ignore[attr-defined]
                out = bridge.info() if bridge else self._aios.dispatch("platform")
            except Exception:
                out = self._aios.dispatch("platform")
            return (out, False)

        elif choice == "9":
            return (self._aios.dispatch("plugins"), False)

        else:
            return (f"Unknown option '{choice}'. Please choose 0-9.", False)

    def run(self) -> None:
        """Run the blocking menu loop."""
        while True:
            print(self.render_menu())
            try:
                choice = input(f"  {_BOLD}Choose [0-9]:{_RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting menu.")
                break
            output, should_exit = self.handle_choice(choice)
            if output:
                print(f"\n{output}\n")
            if should_exit:
                break
