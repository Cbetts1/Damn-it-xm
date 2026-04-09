# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa — Autonomous Universal Resource Architecture
==================================================
Main entry point and CLI dispatcher (importable as aura.main).

Usage:
  python main.py [command]
  python -m aura [command]
  aura [command]          (after pip install)

Commands:
  shell     Start the interactive AURa shell (default)
  server    Start only the API server + dashboard
  monitor   Start the TUI live monitor
  status    Print system status and exit
  ask <q>   Ask the AI engine a question and exit
"""

from __future__ import annotations

import sys
import os
import signal

from aura.config import AURaConfig
from aura.os_core.ai_os import AIOS
from aura.utils import get_logger

_logger = get_logger("aura.main")


def _setup_signal_handlers(aios: AIOS) -> None:
    """Register SIGINT/SIGTERM handlers for graceful shutdown."""
    def _shutdown(signum, frame):
        print("\n[AURa] Received shutdown signal — stopping…")
        aios.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)


def cmd_shell(aios: AIOS) -> None:
    """Start the interactive AURa shell."""
    from aura.shell.shell import AURaShell
    shell = AURaShell(aios)
    shell.run()


def cmd_server(aios: AIOS) -> None:
    """Run only the API server and dashboard (blocking)."""
    port = aios._config.server.port
    print(f"[AURa] Server running — http://localhost:{port}/dashboard")
    print("[AURa] Press Ctrl+C to stop.")
    try:
        signal.pause()
    except (AttributeError, KeyboardInterrupt):
        # signal.pause() not available on Windows
        import time
        while True:
            time.sleep(1)


def cmd_monitor(aios: AIOS) -> None:
    """Start the TUI live monitor."""
    from aura.command_center.monitor import TUIMonitor
    monitor = TUIMonitor(aios)
    monitor.start()


def cmd_status(aios: AIOS) -> None:
    """Print system status and exit."""
    status = aios.status()
    print(f"AURa v{status['version']}  |  Uptime: {status['uptime_human']}")
    for comp, state in status["components"].items():
        icon = "✅" if "online" in state or "ready" in state or "running" in state else "⚠️ "
        print(f"  {icon}  {comp:<22} {state}")


def cmd_ask(aios: AIOS, question: str) -> None:
    """Ask the AI engine a single question and print the response."""
    resp = aios.ai_engine.ask(question)
    print(resp.text)


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    config = AURaConfig.from_env()

    # Parse command
    command = argv[0].lower() if argv else "shell"
    extra = argv[1:] if len(argv) > 1 else []

    # Boot the AI OS
    aios = AIOS(config)
    aios.start()
    _setup_signal_handlers(aios)

    try:
        if command == "shell":
            cmd_shell(aios)
        elif command == "server":
            cmd_server(aios)
        elif command == "monitor":
            cmd_monitor(aios)
        elif command == "status":
            cmd_status(aios)
        elif command == "ask":
            question = " ".join(extra) if extra else "Hello AURa"
            cmd_ask(aios, question)
        else:
            # Treat the entire argv as a question
            question = " ".join(argv)
            cmd_ask(aios, question)
    finally:
        aios.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
