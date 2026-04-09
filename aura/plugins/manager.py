"""
AURa Plugin Manager
====================
Provides an abstract base class for AURa plugins and a registry/dispatcher
that routes shell commands to the appropriate plugin.

Classes:
  • AURaPlugin      — abstract base for all plugins
  • PluginManager   — register, discover, and dispatch plugins
  • SystemInfoPlugin — built-in: detailed system info via 'sysinfo'
  • StoragePlugin    — built-in: key-value store commands
"""

from __future__ import annotations

import os
import platform
import sys
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TYPE_CHECKING

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.plugins")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class AURaPlugin(ABC):
    """
    Abstract base class for all AURa plugins.

    Subclasses must implement :attr:`name`, :attr:`version`,
    :attr:`description`, :attr:`commands`, and :meth:`execute`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier (e.g. "system-info")."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string (e.g. "1.0.0")."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short human-readable description."""

    @abstractmethod
    def commands(self) -> Dict[str, str]:
        """
        Return a mapping of ``{command_name: short_description}``.

        The keys are the shell-level command strings that this plugin handles.
        """

    @abstractmethod
    def execute(self, command: str, args: List[str], aios: "AIOS") -> str:
        """
        Run *command* with *args* in the context of *aios*.

        Returns a string to be displayed to the user.
        """


# ---------------------------------------------------------------------------
# Built-in plugins
# ---------------------------------------------------------------------------

class SystemInfoPlugin(AURaPlugin):
    """Built-in plugin that reports detailed system information."""

    @property
    def name(self) -> str:
        return "system-info"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Detailed system information via the 'sysinfo' command."

    def commands(self) -> Dict[str, str]:
        return {"sysinfo": "Print detailed system and runtime information"}

    def execute(self, command: str, args: List[str], aios: "AIOS") -> str:
        if command != "sysinfo":
            return f"Unknown command '{command}'"
        lines = [
            "── System Information ──────────────────────",
            f"  Python      : {sys.version.split()[0]}",
            f"  Platform    : {platform.platform()}",
            f"  System      : {platform.system()} {platform.release()}",
            f"  Machine     : {platform.machine()}",
            f"  Processor   : {platform.processor() or 'unknown'}",
            f"  Node        : {platform.node()}",
            f"  Arch        : {platform.architecture()[0]}",
            f"  CWD         : {os.getcwd()}",
            f"  Home        : {os.path.expanduser('~')}",
            f"  PID         : {os.getpid()}",
            f"  Argv[0]     : {sys.argv[0]}",
        ]
        # Try to add memory info on Linux
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo") as fh:
                    for line in fh:
                        if line.startswith("MemTotal"):
                            kb = int(line.split()[1])
                            lines.append(f"  MemTotal    : {kb // 1024} MB")
                            break
            except Exception:
                pass
        return "\n".join(lines)


class StoragePlugin(AURaPlugin):
    """Built-in plugin that wraps the persistence engine with simple commands."""

    @property
    def name(self) -> str:
        return "storage"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Key-value store commands backed by the AURa persistence engine."

    def commands(self) -> Dict[str, str]:
        return {
            "store":    "store <namespace> <key> <value>  — persist a value",
            "retrieve": "retrieve <namespace> <key>       — retrieve a value",
            "listkeys": "listkeys <namespace>              — list all keys",
        }

    def execute(self, command: str, args: List[str], aios: "AIOS") -> str:
        try:
            persistence = getattr(aios, "persistence", None)
            if persistence is None:
                return "Persistence engine not available."
        except Exception:
            return "Persistence engine not available."

        if command == "store":
            if len(args) < 3:
                return "Usage: store <namespace> <key> <value>"
            ns, key, value = args[0], args[1], " ".join(args[2:])
            try:
                persistence.set(ns, key, value)
                return f"Stored [{ns}] {key} = {value}"
            except Exception as exc:
                return f"store error: {exc}"

        elif command == "retrieve":
            if len(args) < 2:
                return "Usage: retrieve <namespace> <key>"
            ns, key = args[0], args[1]
            val = persistence.get(ns, key)
            if val is None:
                return f"Key '{key}' not found in namespace '{ns}'."
            return f"[{ns}] {key} = {val}"

        elif command == "listkeys":
            if not args:
                return "Usage: listkeys <namespace>"
            ns = args[0]
            keys = persistence.list_keys(ns)
            if not keys:
                return f"No keys in namespace '{ns}'."
            return f"Keys in [{ns}]:\n" + "\n".join(f"  • {k}" for k in keys)

        return f"Unknown storage command '{command}'"


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------

class PluginManager:
    """
    Registry and dispatcher for AURa plugins.

    Plugins register themselves by name; commands are dispatched to the plugin
    that owns them.  Built-in plugins are loaded via :meth:`load_builtin_plugins`.
    """

    def __init__(self, plugins_dir: Optional[str] = None) -> None:
        self._plugins_dir = plugins_dir or os.path.join(
            os.path.expanduser("~"), ".aura", "plugins"
        )
        self._plugins: Dict[str, AURaPlugin] = {}
        self._command_map: Dict[str, str] = {}  # command → plugin name
        self._logger = get_logger("aura.plugins.manager")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, plugin: AURaPlugin) -> None:
        """Register *plugin* and map its commands to it."""
        if not isinstance(plugin, AURaPlugin):
            raise TypeError(f"Expected AURaPlugin, got {type(plugin)}")
        self._plugins[plugin.name] = plugin
        for cmd in plugin.commands():
            if cmd in self._command_map:
                self._logger.warning(
                    "Command '%s' already owned by '%s'; overriding with '%s'",
                    cmd, self._command_map[cmd], plugin.name,
                )
            self._command_map[cmd] = plugin.name
        self._logger.info("Registered plugin '%s' v%s", plugin.name, plugin.version)

    def unregister(self, name: str) -> None:
        """Remove the plugin named *name* and deregister its commands."""
        plugin = self._plugins.pop(name, None)
        if plugin is None:
            return
        for cmd in plugin.commands():
            self._command_map.pop(cmd, None)
        self._logger.info("Unregistered plugin '%s'", name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[AURaPlugin]:
        """Return the plugin with the given *name*, or None."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[Dict]:
        """Return a list of dicts describing each registered plugin."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "commands": p.commands(),
            }
            for p in self._plugins.values()
        ]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, command: str, args: List[str], aios: "AIOS") -> Optional[str]:
        """
        Find the plugin that owns *command* and execute it.

        Returns the plugin's output string, or ``None`` if no plugin
        handles *command*.
        """
        plugin_name = self._command_map.get(command)
        if plugin_name is None:
            return None
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return None
        try:
            return plugin.execute(command, args, aios)
        except Exception as exc:
            self._logger.error("Plugin '%s' error for command '%s': %s", plugin_name, command, exc)
            return f"Plugin error: {exc}"

    # ------------------------------------------------------------------
    # Built-in plugins
    # ------------------------------------------------------------------

    def load_builtin_plugins(self) -> None:
        """Register all built-in plugins."""
        for plugin in (SystemInfoPlugin(), StoragePlugin()):
            try:
                self.register(plugin)
            except Exception as exc:
                self._logger.error("Failed to load built-in plugin: %s", exc)
        self._logger.info("Built-in plugins loaded (%d total)", len(self._plugins))
