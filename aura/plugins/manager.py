"""
AURa Plugin Manager
====================
Plugin/extension model for the AURa AI OS.

Features:
  • ``AURaPlugin`` — abstract base class for all plugins.
  • ``PluginManager`` — register, dispatch, and list plugins.
  • Built-in plugins: ``SystemInfoPlugin``, ``StoragePlugin``.

Zero required external dependencies (stdlib only).

Usage::

    from aura.plugins.manager import PluginManager, SystemInfoPlugin

    mgr = PluginManager()
    mgr.register(SystemInfoPlugin())
    result = mgr.dispatch("sysinfo")
    print(result)
"""

from __future__ import annotations

import abc
import os
import platform
import shutil
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.plugins")


# ---------------------------------------------------------------------------
# AURaPlugin — Abstract base class
# ---------------------------------------------------------------------------

class AURaPlugin(abc.ABC):
    """
    Abstract base class for all AURa plugins.

    Subclasses must implement:
    - :attr:`name` — the unique command name used to dispatch the plugin.
    - :attr:`description` — a short description for the ``help`` command.
    - :meth:`execute` — the plugin's main entry point.

    Optionally override:
    - :meth:`on_load` — called once when the plugin is registered.
    - :meth:`on_unload` — called when the plugin is unregistered (not yet used).
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique command name (e.g. ``"sysinfo"``)."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """One-line description shown in the help listing."""

    @abc.abstractmethod
    def execute(self, aios: "AIOS", args: List[str]) -> str:
        """
        Run the plugin and return a string to display in the shell.

        Parameters
        ----------
        aios:
            The running :class:`~aura.os_core.ai_os.AIOS` instance.
        args:
            Additional tokens from the shell input.
        """

    def on_load(self, aios: "AIOS") -> None:
        """Called when the plugin is registered with :class:`PluginManager`."""

    def on_unload(self, aios: "AIOS") -> None:
        """Called when the plugin is unregistered from :class:`PluginManager`."""


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------

class PluginManager:
    """
    Registry and dispatcher for :class:`AURaPlugin` instances.

    Parameters
    ----------
    aios:
        Optional reference to the running AIOS instance. If provided,
        ``on_load`` is called on every registered plugin.
    """

    def __init__(self, aios: Optional["AIOS"] = None) -> None:
        self._aios = aios
        self._plugins: Dict[str, AURaPlugin] = {}
        _logger.debug("PluginManager created")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, plugin: AURaPlugin) -> None:
        """
        Register *plugin*.

        Raises :class:`ValueError` if a plugin with the same name is already
        registered.
        """
        pname = plugin.name.lower()
        if pname in self._plugins:
            raise ValueError(f"Plugin {pname!r} is already registered")
        self._plugins[pname] = plugin
        _logger.info("Plugin registered: %s — %s", pname, plugin.description)
        if self._aios is not None:
            try:
                plugin.on_load(self._aios)
            except Exception as exc:
                _logger.warning("Plugin on_load error (%s): %s", pname, exc)

    def unregister(self, name: str) -> None:
        """Unregister the plugin named *name* (case-insensitive)."""
        pname = name.lower()
        plugin = self._plugins.pop(pname, None)
        if plugin is None:
            raise KeyError(f"Plugin {pname!r} is not registered")
        _logger.info("Plugin unregistered: %s", pname)
        if self._aios is not None:
            try:
                plugin.on_unload(self._aios)
            except Exception as exc:
                _logger.warning("Plugin on_unload error (%s): %s", pname, exc)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, command: str, args: Optional[List[str]] = None) -> Optional[str]:
        """
        Dispatch *command* to the matching plugin.

        Returns the plugin's output string, or ``None`` if no plugin
        matches *command*.
        """
        plugin = self._plugins.get(command.lower())
        if plugin is None:
            return None
        _args = args or []
        try:
            return plugin.execute(self._aios, _args)  # type: ignore[arg-type]
        except Exception as exc:
            _logger.error("Plugin %s raised: %s", plugin.name, exc)
            return f"Plugin error ({plugin.name}): {exc}"

    def handles(self, command: str) -> bool:
        """Return ``True`` if a plugin is registered for *command*."""
        return command.lower() in self._plugins

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_plugins(self) -> List[Dict[str, str]]:
        """Return a list of dicts with ``name`` and ``description`` keys."""
        return [
            {"name": p.name, "description": p.description}
            for p in sorted(self._plugins.values(), key=lambda x: x.name)
        ]

    def __len__(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:  # pragma: no cover
        names = sorted(self._plugins)
        return f"PluginManager(plugins={names!r})"


# ---------------------------------------------------------------------------
# Built-in plugins
# ---------------------------------------------------------------------------

class SystemInfoPlugin(AURaPlugin):
    """Built-in plugin: reports host system information."""

    @property
    def name(self) -> str:
        return "sysinfo"

    @property
    def description(self) -> str:
        return "Display host system information (OS, CPU, Python)"

    def execute(self, aios: "AIOS", args: List[str]) -> str:
        lines = [
            "── System Information ─────────────────────────────",
            f"  OS          : {platform.system()} {platform.release()}",
            f"  OS version  : {platform.version()}",
            f"  Machine     : {platform.machine()}",
            f"  Processor   : {platform.processor() or '(unknown)'}",
            f"  Python      : {platform.python_version()} ({platform.python_implementation()})",
            f"  CPU count   : {os.cpu_count() or '?'}",
            f"  Hostname    : {platform.node()}",
        ]
        try:
            total, used, free = shutil.disk_usage(os.getcwd())
            lines += [
                f"  Disk total  : {self._fmt(total)}",
                f"  Disk free   : {self._fmt(free)}",
            ]
        except OSError:
            pass
        return "\n".join(lines)

    @staticmethod
    def _fmt(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n //= 1024
        return f"{n:.1f} PB"


class StoragePlugin(AURaPlugin):
    """Built-in plugin: reports AURa persistence storage stats."""

    @property
    def name(self) -> str:
        return "storage"

    @property
    def description(self) -> str:
        return "Show AURa persistence storage statistics"

    def execute(self, aios: "AIOS", args: List[str]) -> str:
        # Use public property to access the persistence engine.
        engine = getattr(aios, "persistence", None)
        if engine is None:
            return "storage: persistence engine not available"

        try:
            namespaces = engine.namespaces()
            lines = ["── Persistence Storage ─────────────────────────────"]
            if not namespaces:
                lines.append("  (no data stored yet)")
            else:
                for ns in namespaces:
                    keys = engine.list_keys(ns)
                    files = engine.list_files(ns)
                    lines.append(
                        f"  [{ns}]  {len(keys)} key(s)  {len(files)} file(s)"
                    )
            return "\n".join(lines)
        except Exception as exc:
            return f"storage: error reading persistence engine: {exc}"
