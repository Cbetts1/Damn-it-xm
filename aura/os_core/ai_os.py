"""
AURa AI OS (AIOS)
=================
The central orchestrator and "bridge" of the AURa virtual system.

Responsibilities:
  • Bootstraps and manages all virtual components (Cloud, CPU, Server)
  • Routes queries and tasks to the AI engine
  • Exposes a unified status/metrics API consumed by the Command Center and Shell
  • Handles inter-component events via the shared EventBus
  • Enforces resource policy and health checks
  • Provides a command dispatch interface for the Shell

The AI OS is designed to be the *only physical component* — all compute,
storage, and serving is done through its managed virtual layer.
"""

from __future__ import annotations

import os
import signal
import time
import threading
from typing import Any, Callable, Dict, List, Optional

from aura.config import AURaConfig
from aura.utils import get_logger, format_uptime, utcnow, EVENT_BUS
from aura.ai_engine.engine import AIEngine
from aura.cloud.virtual_cloud import VirtualCloud
from aura.cpu.virtual_cpu import VirtualCPU, TaskPriority
from aura.server.virtual_server import VirtualServer
from aura.persistence.store import PersistenceEngine
from aura.adapters.android_bridge import AndroidBridge, detect_capabilities, PlatformCapabilities
from aura.plugins.manager import PluginManager

_logger = get_logger("aura.os")

# ---------------------------------------------------------------------------
# AIOS
# ---------------------------------------------------------------------------

class AIOS:
    """
    AURa AI Operating System.
    The single physical AI component that bridges all virtual infrastructure.
    """

    VERSION = "1.0.0"

    def __init__(self, config: Optional[AURaConfig] = None) -> None:
        self._config = config or AURaConfig.from_env()
        self._start_time: Optional[float] = None
        self._running = False
        self._lock = threading.Lock()
        self._logger = get_logger("aura.os")

        # Subsystems — initialised lazily in start()
        self._ai_engine: Optional[AIEngine] = None
        self._cloud: Optional[VirtualCloud] = None
        self._cpu: Optional[VirtualCPU] = None
        self._server: Optional[VirtualServer] = None
        self._persistence: Optional[PersistenceEngine] = None
        self._capabilities: Optional[PlatformCapabilities] = None
        self._android_bridge: Optional[AndroidBridge] = None
        self._plugin_manager: Optional[PluginManager] = None

        # OS-level command registry
        self._commands: Dict[str, Callable] = {}

        # Event subscriptions
        EVENT_BUS.subscribe("*", self._on_event)

    # ------------------------------------------------------------------
    # Properties — expose subsystems (read-only after boot)
    # ------------------------------------------------------------------

    @property
    def ai_engine(self) -> AIEngine:
        assert self._ai_engine is not None, "AIOS not started"
        return self._ai_engine

    @property
    def cloud(self) -> VirtualCloud:
        assert self._cloud is not None, "AIOS not started"
        return self._cloud

    @property
    def cpu(self) -> VirtualCPU:
        assert self._cpu is not None, "AIOS not started"
        return self._cpu

    @property
    def server(self) -> VirtualServer:
        assert self._server is not None, "AIOS not started"
        return self._server

    @property
    def persistence(self) -> Optional[PersistenceEngine]:
        return self._persistence

    @property
    def capabilities(self) -> Optional[PlatformCapabilities]:
        return self._capabilities

    @property
    def android_bridge(self) -> Optional[AndroidBridge]:
        return self._android_bridge

    @property
    def plugin_manager(self) -> Optional[PluginManager]:
        return self._plugin_manager

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Boot the AI OS and all virtual components."""
        if self._running:
            return

        self._logger.info("=" * 60)
        self._logger.info("  AURa v%s — Booting AI OS …", self.VERSION)
        self._logger.info("=" * 60)

        # 1. AI Engine (the brain — the only "physical" AI component)
        self._logger.info("[1/4] Initialising AI Engine (%s)…", self._config.ai_engine.backend)
        self._ai_engine = AIEngine(self._config.ai_engine)

        # 2. Virtual Cloud (large model storage + distributed compute)
        self._logger.info("[2/4] Provisioning Virtual Cloud (%d nodes)…", self._config.cloud.compute_nodes)
        self._cloud = VirtualCloud(self._config.cloud)

        # 3. Virtual CPU (task scheduler)
        self._logger.info("[3/4] Starting Virtual CPU (%d vCores)…", self._config.cpu.virtual_cores)
        self._cpu = VirtualCPU(self._config.cpu)
        self._cpu.start()

        # 4. Virtual Server (HTTP API + dashboard)
        self._logger.info("[4/4] Starting Virtual Server (port %d)…", self._config.server.port)
        self._server = VirtualServer(self._config.server)
        self._server.start(self)

        # Register the AI model in the cloud registry
        self._cloud.register_model(
            model_id="aura-engine-001",
            model_name=self._config.ai_engine.model_name,
            size_bytes=350_000_000,  # approximate
            backend=self._config.ai_engine.backend,
        )

        # 5. Platform capabilities detection
        self._logger.info("[5/6] Detecting platform capabilities…")
        try:
            self._capabilities = detect_capabilities()
            self._logger.info(
                "Platform: android=%s termux=%s linux=%s arch=%s",
                self._capabilities.is_android,
                self._capabilities.is_termux,
                self._capabilities.is_linux,
                self._capabilities.arch,
            )
            if self._capabilities.is_android or self._capabilities.is_termux:
                self._android_bridge = AndroidBridge(self._capabilities)
                self._logger.info("AndroidBridge initialised.")
        except Exception as exc:
            self._logger.warning("Platform detection failed: %s", exc)

        # 6. Persistence engine + Plugin manager
        self._logger.info("[6/6] Initialising Persistence Engine…")
        try:
            os.makedirs(os.path.dirname(self._config.persistence_db) or ".", exist_ok=True)
            self._persistence = PersistenceEngine(self._config.persistence_db)
        except Exception as exc:
            self._logger.warning("PersistenceEngine init failed: %s", exc)

        try:
            self._plugin_manager = PluginManager()
            self._plugin_manager.load_builtin_plugins()
        except Exception as exc:
            self._logger.warning("PluginManager init failed: %s", exc)

        self._start_time = time.monotonic()
        self._running = True

        self._logger.info("=" * 60)
        self._logger.info("  AURa AI OS is ONLINE")
        self._logger.info("  Dashboard : http://localhost:%d/dashboard", self._config.server.port)
        self._logger.info("  API       : http://localhost:%d/api/v1/", self._config.server.port)
        self._logger.info("=" * 60)

        EVENT_BUS.publish("aios.started", {"version": self.VERSION})

    def stop(self) -> None:
        """Gracefully shut down all virtual components."""
        if not self._running:
            return
        self._logger.info("AURa AI OS shutting down…")
        if self._server:
            self._server.stop()
        if self._cpu:
            self._cpu.stop()
        self._running = False
        EVENT_BUS.publish("aios.stopped", {})
        self._logger.info("AURa AI OS stopped.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ------------------------------------------------------------------
    # Status & Metrics
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """High-level system status snapshot."""
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0
        result = {
            "system": "AURa",
            "version": self.VERSION,
            "running": self._running,
            "uptime_seconds": round(uptime, 1),
            "uptime_human": format_uptime(uptime),
            "timestamp": utcnow(),
            "components": {
                "ai_os": "online" if self._running else "offline",
                "ai_engine": "ready" if (self._ai_engine and self._ai_engine.is_ready()) else "not_ready",
                "virtual_cloud": "online" if self._cloud else "offline",
                "virtual_cpu": "running" if (self._cpu and self._cpu._running) else "stopped",
                "virtual_server": "running" if (self._server and self._server._thread and self._server._thread.is_alive()) else "stopped",
                "persistence": "online" if self._persistence else "offline",
                "plugin_manager": f"{len(self._plugin_manager._plugins)} plugins" if self._plugin_manager else "offline",
            },
        }
        if self._capabilities:
            result["platform"] = {
                "android": self._capabilities.is_android,
                "termux": self._capabilities.is_termux,
                "linux": self._capabilities.is_linux,
                "arch": self._capabilities.arch,
            }
        return result

    def metrics(self) -> dict:
        """Detailed metrics for all components (consumed by the Command Center)."""
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0
        return {
            "version": self.VERSION,
            "uptime_seconds": round(uptime, 1),
            "ai_backend": self._ai_engine.backend_name if self._ai_engine else "none",
            "model_name": self._ai_engine.model_name if self._ai_engine else "none",
            "cloud": self._cloud.metrics() if self._cloud else {},
            "cpu": self._cpu.metrics() if self._cpu else {},
            "server": self._server.metrics() if self._server else {},
            "timestamp": utcnow(),
        }

    # ------------------------------------------------------------------
    # Command dispatch (used by the Shell)
    # ------------------------------------------------------------------

    def dispatch(self, command: str, args: Optional[List[str]] = None) -> str:
        """
        Dispatch a shell command to the AI OS.
        Returns a string response to display in the shell.
        """
        args = args or []
        cmd = command.strip().lower()

        if cmd == "status":
            s = self.status()
            lines = [f"AURa v{s['version']}  |  Uptime: {s['uptime_human']}"]
            for comp, state in s["components"].items():
                icon = "✅" if "online" in state or "ready" in state or "running" in state else "⚠️ "
                lines.append(f"  {icon}  {comp:<20} {state}")
            return "\n".join(lines)

        elif cmd == "metrics":
            m = self.metrics()
            cloud = m["cloud"]
            cpu = m["cpu"]
            lines = [
                f"── Virtual Cloud ──────────────────────────────",
                f"  Nodes      : {cloud.get('nodes_online', '?')}/{cloud.get('nodes_total', '?')} online",
                f"  CPU        : {cloud.get('cpu_utilisation_pct', 0):.1f}%",
                f"  Memory     : {cloud.get('memory_utilisation_pct', 0):.1f}%",
                f"  Region     : {cloud.get('region', '?')}",
                f"── Virtual CPU ────────────────────────────────",
                f"  vCores     : {cpu.get('virtual_cores', '?')} @ {cpu.get('clock_speed_ghz', '?')} GHz",
                f"  Completed  : {cpu.get('tasks_completed', 0)} tasks",
                f"  Throughput : {cpu.get('throughput_tps', 0):.3f} tasks/s",
                f"  Queue depth: {cpu.get('queue_depth', 0)}",
            ]
            return "\n".join(lines)

        elif cmd == "cloud":
            return self.dispatch("metrics")  # alias

        elif cmd == "cpu":
            m = self.cpu.metrics()
            lines = [
                f"Virtual CPU — {m['architecture']}",
                f"  vCores  : {m['virtual_cores']} ({m['virtual_cores'] * m['threads_per_core']} threads)",
                f"  Clock   : {m['clock_speed_ghz']} GHz",
                f"  L3 Cache: {m['l3_cache_mb']} MB",
                f"  Workers active: {m['workers_active']}",
                f"  Queue depth   : {m['queue_depth']}",
                f"  Tasks done    : {m['tasks_completed']}",
                f"  Tasks failed  : {m['tasks_failed']}",
                f"  Uptime        : {format_uptime(m['uptime_seconds'])}",
            ]
            return "\n".join(lines)

        elif cmd == "server":
            m = self.server.metrics()
            return (
                f"Virtual Server\n"
                f"  Host   : {m['host']}:{m['port']}\n"
                f"  Status : {'running' if m['running'] else 'stopped'}\n"
                f"  Uptime : {format_uptime(m['uptime_seconds'])}\n"
                f"  API    : http://localhost:{m['port']}/api/v1/\n"
                f"  Dash   : http://localhost:{m['port']}/dashboard"
            )

        elif cmd in ("ask", "ai"):
            query = " ".join(args) if args else ""
            if not query:
                return "Usage: ask <your question>"
            resp = self.ai_engine.ask(query)
            return resp.text

        elif cmd == "models":
            models = self.cloud.list_models()
            if not models:
                return "No models registered."
            lines = ["Registered AI models:"]
            for m in models:
                lines.append(f"  • {m['model_name']}  [{m['backend']}]  {m['size_human']}")
            return "\n".join(lines)

        elif cmd == "nodes":
            nodes = self.cloud.list_nodes()
            lines = [f"Cloud Nodes ({len(nodes)} total):"]
            for n in nodes:
                lines.append(
                    f"  {n['node_id']}  {n['status']}  "
                    f"CPU:{n['cpu_utilisation']:.0f}%  MEM:{n['memory_utilisation']:.0f}%"
                )
            return "\n".join(lines)

        elif cmd == "tasks":
            tasks = self.cpu.list_tasks()
            if not tasks:
                return "No tasks recorded."
            lines = [f"CPU Tasks ({len(tasks)} total):"]
            for t in tasks[-20:]:
                lines.append(
                    f"  [{t['status']:<10}] {t['task_id']}  {t['name']}  {t['duration_ms']:.0f}ms"
                )
            return "\n".join(lines)

        elif cmd == "plan":
            task_desc = " ".join(args) if args else "optimise the AURa virtual system"
            resp = self.ai_engine.plan_task(task_desc)
            return resp.text

        elif cmd == "analyse":
            resp = self.ai_engine.analyse_metrics(self.metrics())
            return resp.text

        elif cmd == "history":
            hist = self.ai_engine.get_history()
            if not hist:
                return "No conversation history."
            lines = []
            for msg in hist[-20:]:
                role = "You" if msg["role"] == "user" else "AURa"
                lines.append(f"{role}: {msg['content'][:120]}")
            return "\n".join(lines)

        elif cmd == "clear_history":
            self.ai_engine.clear_history()
            return "Conversation history cleared."

        elif cmd == "version":
            return f"AURa v{self.VERSION} — Autonomous Universal Resource Architecture"

        elif cmd in ("help", "?"):
            return (
                "AURa OS Commands:\n"
                "  status        — system health overview\n"
                "  metrics       — detailed component metrics\n"
                "  cloud         — virtual cloud metrics\n"
                "  cpu           — virtual CPU metrics\n"
                "  server        — virtual server info\n"
                "  nodes         — list cloud compute nodes\n"
                "  models        — list registered AI models\n"
                "  tasks         — list CPU tasks\n"
                "  ask <query>   — query the AI engine\n"
                "  plan <task>   — AI-generated task execution plan\n"
                "  analyse       — AI analysis of current metrics\n"
                "  history       — show conversation history\n"
                "  clear_history — clear conversation history\n"
                "  bash <cmd>    — execute a shell command\n"
                "  store <ns> <key> <value> — persist a value\n"
                "  retrieve <ns> <key>      — retrieve a value\n"
                "  platform      — show platform capabilities\n"
                "  plugins       — list loaded plugins\n"
                "  menu          — show the text menu\n"
                "  version       — show AURa version\n"
                "  help          — show this help\n"
                "  exit / quit   — exit the AURa shell"
            )

        elif cmd == "bash":
            from aura.shell.commands import ShellCommandExecutor
            executor = ShellCommandExecutor()
            shell_cmd = " ".join(args)
            if not shell_cmd:
                return "Usage: bash <command>"
            return executor.execute(shell_cmd)

        elif cmd == "store":
            if len(args) < 3:
                return "Usage: store <namespace> <key> <value>"
            if self._persistence is None:
                return "Persistence engine not available."
            ns, key, value = args[0], args[1], " ".join(args[2:])
            try:
                self._persistence.set(ns, key, value)
                return f"Stored [{ns}] {key} = {value}"
            except Exception as exc:
                return f"store error: {exc}"

        elif cmd == "retrieve":
            if len(args) < 2:
                return "Usage: retrieve <namespace> <key>"
            if self._persistence is None:
                return "Persistence engine not available."
            ns, key = args[0], args[1]
            val = self._persistence.get(ns, key)
            if val is None:
                return f"Key '{key}' not found in namespace '{ns}'."
            return f"[{ns}] {key} = {val}"

        elif cmd == "platform":
            if self._capabilities is None:
                return "Platform capabilities not yet detected."
            if self._android_bridge:
                return self._android_bridge.info()
            c = self._capabilities
            lines = [
                "── Platform Capabilities ────────────────────",
                f"  Android : {c.is_android}",
                f"  Termux  : {c.is_termux}",
                f"  Linux   : {c.is_linux}",
                f"  Windows : {c.is_windows}",
                f"  Arch    : {c.arch}",
                f"  Release : {c.os_release}",
                f"  bash={c.has_bash}  git={c.has_git}  curl={c.has_curl}",
                f"  ssh={c.has_ssh}  pkg={c.has_pkg}  apt={c.has_apt}  pip={c.has_pip}",
            ]
            return "\n".join(lines)

        elif cmd == "plugins":
            if self._plugin_manager is None:
                return "Plugin manager not available."
            plugins = self._plugin_manager.list_plugins()
            if not plugins:
                return "No plugins loaded."
            lines = [f"Loaded plugins ({len(plugins)}):"]
            for p in plugins:
                cmds = ", ".join(p["commands"].keys())
                lines.append(f"  • {p['name']} v{p['version']} — {p['description']}")
                lines.append(f"    Commands: {cmds}")
            return "\n".join(lines)

        elif cmd == "menu":
            from aura.shell.commands import MenuWorkspace
            return MenuWorkspace(self).render_menu()

        else:
            # Check plugin manager before falling back to AI
            if self._plugin_manager:
                plugin_result = self._plugin_manager.dispatch(cmd, args, self)
                if plugin_result is not None:
                    return plugin_result
            # Unknown command → route to AI engine
            resp = self.ai_engine.ask(command + (" " + " ".join(args) if args else ""))
            return resp.text

    # ------------------------------------------------------------------
    # Internal event handler
    # ------------------------------------------------------------------

    def _on_event(self, event_type: str, payload: Any) -> None:
        if event_type != "*":  # avoid double-logging
            self._logger.debug("Event received: %s", event_type)
