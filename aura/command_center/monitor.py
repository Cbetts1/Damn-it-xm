# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Command Center
===================
The Command Center provides two interfaces for overseeing the AURa system:

1. Web Dashboard  — served at http://localhost:<port>/dashboard
   - Real-time metrics for all virtual components
   - Embedded AI chat panel
   - Auto-refreshing (no page reload needed)

2. TUI Monitor    — terminal-based live status view (requires no browser)

The Command Center reads system state entirely through the AI OS,
so it is a pure "observer" layer with zero direct coupling to
the underlying virtual hardware.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from typing import Optional, TYPE_CHECKING

from aura.utils import get_logger, format_uptime

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.command_center")

# ---------------------------------------------------------------------------
# TUI Monitor (works in any terminal, no extra deps)
# ---------------------------------------------------------------------------

_CLEAR = "\033[2J\033[H"
_BOLD = "\033[1m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_MAGENTA = "\033[95m"
_RESET = "\033[0m"
_DIM = "\033[2m"


def _bar(pct: float, width: int = 20) -> str:
    """ASCII progress bar."""
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    colour = _GREEN if pct < 60 else _YELLOW if pct < 85 else "\033[91m"
    return f"{colour}[{bar}]{_RESET} {pct:.1f}%"


def _render_frame(aios: "AIOS") -> str:
    """Render a full-screen TUI frame from current AIOS metrics."""
    m = aios.metrics()
    s = aios.status()
    cloud = m.get("cloud", {})
    cpu = m.get("cpu", {})
    srv = m.get("server", {})
    uptime = format_uptime(m.get("uptime_seconds", 0))
    port = srv.get("port", 8000)

    lines = [
        f"{_CLEAR}",
        f"{_BOLD}{_CYAN}  ╔═══════════════════════════════════════════════════╗{_RESET}",
        f"{_BOLD}{_CYAN}  ║     AURa v{aios.VERSION}  —  AI OS Command Center         ║{_RESET}",
        f"{_BOLD}{_CYAN}  ╚═══════════════════════════════════════════════════╝{_RESET}",
        f"",
        f"  {_BOLD}System:{_RESET}  uptime {uptime}   AI backend: {m.get('ai_backend','?')}   model: {m.get('model_name','?')}",
        f"",
        f"  {_BOLD}{_MAGENTA}◈ Components{_RESET}",
    ]
    for comp, state in s["components"].items():
        icon = f"{_GREEN}●{_RESET}" if "online" in state or "ready" in state or "running" in state else f"{_YELLOW}◐{_RESET}"
        lines.append(f"    {icon}  {comp:<22} {state}")

    lines += [
        f"",
        f"  {_BOLD}{_CYAN}☁  Virtual Cloud{_RESET}   region: {cloud.get('region','?')}",
        f"    Nodes   : {cloud.get('nodes_online','?')}/{cloud.get('nodes_total','?')} online",
        f"    CPU     : {_bar(cloud.get('cpu_utilisation_pct', 0))}",
        f"    Memory  : {_bar(cloud.get('memory_utilisation_pct', 0))}",
        f"",
        f"  {_BOLD}{_MAGENTA}⚙  Virtual CPU{_RESET}   arch: {cpu.get('architecture','?')}   {cpu.get('virtual_cores','?')} vCores @ {cpu.get('clock_speed_ghz','?')} GHz",
        f"    Tasks done  : {cpu.get('tasks_completed', 0)}",
        f"    Throughput  : {cpu.get('throughput_tps', 0):.3f} tasks/s",
        f"    Queue depth : {cpu.get('queue_depth', 0)}",
        f"",
        f"  {_BOLD}⛭  Virtual Server{_RESET}   {'running' if srv.get('running') else 'stopped'}",
        f"    API       : http://localhost:{port}/api/v1/",
        f"    Dashboard : http://localhost:{port}/dashboard",
        f"",
        f"  {_DIM}Press Ctrl+C to exit  ·  auto-refresh every 2s{_RESET}",
    ]
    return "\n".join(lines)


class TUIMonitor:
    """
    Terminal User Interface live monitor.
    Displays a continuously-updating overview of all AURa components.
    Run with: aura monitor
    """

    def __init__(self, aios: "AIOS", refresh_interval: float = 2.0) -> None:
        self._aios = aios
        self._interval = refresh_interval
        self._running = False

    def start(self) -> None:
        self._running = True
        try:
            while self._running:
                frame = _render_frame(self._aios)
                sys.stdout.write(frame)
                sys.stdout.flush()
                time.sleep(self._interval)
        except KeyboardInterrupt:
            self._running = False
            print(f"\n{_RESET}")

    def stop(self) -> None:
        self._running = False
