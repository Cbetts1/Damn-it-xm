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

import json
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

        # OS-level command registry — built-ins are handled in dispatch(),
        # custom commands registered via register_command() live here.
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

    # ------------------------------------------------------------------
    # Plugin registry — custom shell commands
    # ------------------------------------------------------------------

    def register_command(self, name: str, fn: Callable) -> None:
        """Register a custom shell command.

        ``fn`` receives ``(aios, args)`` where *aios* is this instance and
        *args* is a ``List[str]`` of additional tokens from the shell input.
        It must return a ``str`` that will be printed in the shell.

        Example::

            def cmd_greet(aios, args):
                return "Hello, " + (" ".join(args) or "world") + "!"

            aios.register_command("greet", cmd_greet)
        """
        self._commands[name.lower()] = fn
        self._logger.info("Custom command registered: %s", name)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _state_path(self) -> str:
        return os.path.join(self._config.data_dir, "state.json")

    def _save_state(self) -> None:
        """Persist model registry, conversation history, and task list."""
        if self._ai_engine is None and self._cloud is None and self._cpu is None:
            return
        state: dict = {}
        if self._ai_engine is not None:
            state["conversation_history"] = self._ai_engine.get_history()
        if self._cloud is not None:
            state["model_registry"] = self._cloud.list_models()
        if self._cpu is not None:
            state["tasks"] = self._cpu.list_tasks()
        state["saved_at"] = utcnow()
        try:
            os.makedirs(self._config.data_dir, exist_ok=True)
            with open(self._state_path(), "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, default=str)
            self._logger.info("State saved to %s", self._state_path())
        except OSError as exc:
            self._logger.warning("Could not save state: %s", exc)

    def _load_state(self) -> None:
        """Restore persisted state if a state file exists."""
        path = self._state_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning("Could not load state from %s: %s", path, exc)
            return

        if self._ai_engine is not None:
            history = state.get("conversation_history", [])
            if history:
                self._ai_engine.load_history(history)
                self._logger.info("Restored %d history entries", len(history))

        if self._cloud is not None:
            for entry in state.get("model_registry", []):
                mid = entry.get("model_id")
                if mid and mid not in {m["model_id"] for m in self._cloud.list_models()}:
                    self._cloud.register_model(
                        model_id=mid,
                        model_name=entry.get("model_name", "unknown"),
                        size_bytes=entry.get("size_bytes", 0),
                        backend=entry.get("backend", "builtin"),
                    )
            self._logger.info("Model registry restored")

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

        # Restore persisted state (history, extra models)
        self._load_state()

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
        # Persist state before tearing down subsystems
        self._save_state()
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
        return {
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
            },
        }

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
            base = (
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
                "  version       — show AURa version\n"
                "  help          — show this help\n"
                "  exit / quit   — exit the AURa shell"
            )
            if self._commands:
                custom = "\n".join(
                    f"  {name:<14}— (custom command)" for name in sorted(self._commands)
                )
                return base + "\n\nCustom commands:\n" + custom
            return base

        elif cmd in self._commands:
            # Custom registered command
            return self._commands[cmd](self, args)

        else:
            # Unknown command → route to AI engine
            resp = self.ai_engine.ask(command + (" " + " ".join(args) if args else ""))
            return resp.text

    # ------------------------------------------------------------------
    # Internal event handler
    # ------------------------------------------------------------------

    def _on_event(self, event_type: str, payload: Any) -> None:
        if event_type != "*":  # avoid double-logging
            self._logger.debug("Event received: %s", event_type)
