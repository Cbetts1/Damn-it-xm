"""
AURa Virtual Server
===================
Provides an HTTP API server backed by FastAPI (if available) or a
stdlib http.server fallback. Exposes:

  GET  /health          — health check
  GET  /api/v1/status   — full system status
  GET  /api/v1/metrics  — metrics for all components
  POST /api/v1/ask      — send a query to the AI engine
  POST /api/v1/task     — submit a CPU task
  GET  /api/v1/cloud    — cloud status
  GET  /api/v1/cpu      — CPU metrics
  GET  /api/v1/models   — registered AI models
  GET  /dashboard       — web command center (HTML)

The AI OS manages the lifecycle of this server.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Callable, Optional
from urllib.parse import urlparse, parse_qs

from aura.config import ServerConfig
from aura.utils import get_logger, utcnow, EVENT_BUS

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.server")

# ---------------------------------------------------------------------------
# HTML dashboard template (single-page, no external dependencies)
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>AURa Command Center</title>
  <style>
    :root {
      --bg: #0a0a12; --surface: #12121e; --card: #1a1a2e;
      --accent: #7c3aed; --accent2: #06b6d4; --text: #e2e8f0;
      --muted: #94a3b8; --success: #10b981; --warn: #f59e0b; --danger: #ef4444;
      --border: #2d2d44; --font: 'Segoe UI', system-ui, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: var(--font); min-height: 100vh; }
    header {
      background: linear-gradient(135deg, var(--surface) 0%, #1e1040 100%);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex; align-items: center; gap: 1rem;
    }
    .logo { font-size: 1.8rem; font-weight: 800; letter-spacing: 0.1em;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .version { color: var(--muted); font-size: 0.8rem; }
    .status-dot { width: 10px; height: 10px; border-radius: 50%;
      background: var(--success); animation: pulse 2s infinite; margin-left: auto; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    main { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.5rem; padding: 2rem; max-width: 1600px; margin: 0 auto; }
    .card { background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; padding: 1.5rem; }
    .card-title { font-size: 0.7rem; letter-spacing: 0.15em; text-transform: uppercase;
      color: var(--muted); margin-bottom: 1rem; }
    .metric-row { display: flex; justify-content: space-between;
      align-items: center; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }
    .metric-row:last-child { border: none; }
    .metric-label { color: var(--muted); font-size: 0.85rem; }
    .metric-value { font-weight: 600; font-size: 0.95rem; }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px;
      font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
    .badge-green { background: #052e1620; color: var(--success); border: 1px solid var(--success); }
    .badge-blue  { background: #0e749020; color: var(--accent2); border: 1px solid var(--accent2); }
    .badge-purple{ background: #4c1d9520; color: var(--accent);  border: 1px solid var(--accent); }
    .progress-bar { background: var(--border); border-radius: 999px; height: 8px;
      overflow: hidden; margin-top: 0.3rem; }
    .progress-fill { height: 100%; border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      transition: width 1s ease; }
    .chat-box { grid-column: 1 / -1; }
    .chat-messages { background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; height: 220px; overflow-y: auto; padding: 1rem;
      font-size: 0.85rem; line-height: 1.6; margin-bottom: 0.8rem; }
    .chat-row { display: flex; gap: 0.5rem; }
    .chat-input { flex: 1; background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 0.6rem 1rem; color: var(--text); font-size: 0.9rem;
      outline: none; }
    .chat-input:focus { border-color: var(--accent); }
    .btn { background: linear-gradient(135deg, var(--accent), #5b21b6);
      color: #fff; border: none; border-radius: 8px; padding: 0.6rem 1.4rem;
      cursor: pointer; font-weight: 600; font-size: 0.9rem; transition: opacity .2s; }
    .btn:hover { opacity: 0.85; }
    .msg-user   { color: var(--accent2); }
    .msg-aura   { color: var(--text); white-space: pre-wrap; }
    .msg-label  { font-weight: 700; margin-right: 0.4rem; font-size: 0.75rem; }
    footer { text-align: center; color: var(--muted); font-size: 0.75rem;
      padding: 1.5rem; border-top: 1px solid var(--border); }
  </style>
</head>
<body>
<header>
  <div class="logo">AURa</div>
  <div>
    <div style="font-weight:600;">Autonomous Universal Resource Architecture</div>
    <div class="version">v1.0.0 · AI OS Command Center</div>
  </div>
  <div class="status-dot" title="All systems operational"></div>
</header>
<main>

  <!-- AI OS Status -->
  <div class="card" id="card-os">
    <div class="card-title">🧠 AI OS</div>
    <div class="metric-row">
      <span class="metric-label">Status</span>
      <span class="badge badge-green" id="os-status">Online</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Version</span>
      <span class="metric-value" id="os-version">1.0.0</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">AI Backend</span>
      <span class="metric-value" id="os-backend">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Uptime</span>
      <span class="metric-value" id="os-uptime">—</span>
    </div>
  </div>

  <!-- Virtual Cloud -->
  <div class="card" id="card-cloud">
    <div class="card-title">☁️ Virtual Cloud</div>
    <div class="metric-row">
      <span class="metric-label">Nodes Online</span>
      <span class="metric-value" id="cloud-nodes">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Region</span>
      <span class="metric-value" id="cloud-region">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">CPU Utilisation</span>
      <span class="metric-value" id="cloud-cpu-pct">—</span>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="cloud-cpu-bar" style="width:0%"></div></div>
    <div class="metric-row" style="margin-top:.8rem">
      <span class="metric-label">Memory</span>
      <span class="metric-value" id="cloud-mem-pct">—</span>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="cloud-mem-bar" style="width:0%"></div></div>
  </div>

  <!-- Virtual CPU -->
  <div class="card" id="card-cpu">
    <div class="card-title">⚙️ Virtual CPU</div>
    <div class="metric-row">
      <span class="metric-label">Architecture</span>
      <span class="metric-value" id="cpu-arch">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">vCores / Clock</span>
      <span class="metric-value" id="cpu-cores">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Tasks Completed</span>
      <span class="metric-value" id="cpu-completed">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Throughput</span>
      <span class="metric-value" id="cpu-tps">—</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Queue Depth</span>
      <span class="metric-value" id="cpu-queue">—</span>
    </div>
  </div>

  <!-- AI Chat -->
  <div class="card chat-box">
    <div class="card-title">💬 AURa AI Assistant</div>
    <div class="chat-messages" id="chat-log">
      <div><span class="msg-label msg-aura">AURa:</span><span class="msg-aura">Hello! I am AURa, your AI OS. Type a message below to interact with the AI engine.</span></div>
    </div>
    <div class="chat-row">
      <input class="chat-input" id="chat-input" placeholder="Ask AURa anything…" autocomplete="off"/>
      <button class="btn" onclick="sendMsg()">Send</button>
    </div>
  </div>

</main>
<footer>AURa v1.0.0 · Free &amp; Open Source · Built with ❤️ by the AURa Project</footer>

<script>
  async function fetchMetrics() {
    try {
      const r = await fetch('/api/v1/metrics');
      const d = await r.json();
      // OS
      document.getElementById('os-version').textContent = d.version || '1.0.0';
      document.getElementById('os-backend').textContent = d.ai_backend || 'builtin';
      document.getElementById('os-uptime').textContent = fmtUptime(d.uptime_seconds || 0);
      // Cloud
      const c = d.cloud || {};
      document.getElementById('cloud-nodes').textContent = (c.nodes_online||0) + ' / ' + (c.nodes_total||0);
      document.getElementById('cloud-region').textContent = c.region || '—';
      document.getElementById('cloud-cpu-pct').textContent = (c.cpu_utilisation_pct||0) + '%';
      document.getElementById('cloud-cpu-bar').style.width = (c.cpu_utilisation_pct||0) + '%';
      document.getElementById('cloud-mem-pct').textContent = (c.memory_utilisation_pct||0) + '%';
      document.getElementById('cloud-mem-bar').style.width = (c.memory_utilisation_pct||0) + '%';
      // CPU
      const cpu = d.cpu || {};
      document.getElementById('cpu-arch').textContent = cpu.architecture || '—';
      document.getElementById('cpu-cores').textContent = (cpu.virtual_cores||0) + ' @ ' + (cpu.clock_speed_ghz||0) + ' GHz';
      document.getElementById('cpu-completed').textContent = cpu.tasks_completed || 0;
      document.getElementById('cpu-tps').textContent = (cpu.throughput_tps||0) + ' tasks/s';
      document.getElementById('cpu-queue').textContent = cpu.queue_depth || 0;
    } catch(e) { console.error(e); }
  }

  function fmtUptime(s) {
    const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = Math.floor(s%60);
    return String(h).padStart(2,'0')+'h '+String(m).padStart(2,'0')+'m '+String(sec).padStart(2,'0')+'s';
  }

  async function sendMsg() {
    const inp = document.getElementById('chat-input');
    const msg = inp.value.trim();
    if (!msg) return;
    inp.value = '';
    const log = document.getElementById('chat-log');
    log.innerHTML += '<div><span class="msg-label msg-user">You:</span><span class="msg-user">' + escHtml(msg) + '</span></div>';
    log.scrollTop = log.scrollHeight;
    try {
      const r = await fetch('/api/v1/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt: msg})
      });
      const d = await r.json();
      log.innerHTML += '<div><span class="msg-label msg-aura">AURa:</span><span class="msg-aura">' + escHtml(d.response || d.error || 'No response') + '</span></div>';
    } catch(e) {
      log.innerHTML += '<div><span class="msg-label msg-aura">AURa:</span><span class="msg-aura">[Error: ' + escHtml(String(e)) + ']</span></div>';
    }
    log.scrollTop = log.scrollHeight;
  }

  document.getElementById('chat-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendMsg();
  });

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  fetchMetrics();
  setInterval(fetchMetrics, 3000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Simple stdlib HTTP server (fallback when FastAPI is not installed)
# ---------------------------------------------------------------------------

class _AURaHandler(BaseHTTPRequestHandler):
    """Minimal HTTP request handler for the Virtual Server."""

    aios: Optional["AIOS"] = None  # set by VirtualServer.start()

    def log_message(self, fmt, *args):  # suppress default logging
        _logger.debug("HTTP %s %s", self.command, self.path)

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        aios = self.__class__.aios

        if path in ("/health", "/"):
            self._send_json(200, {"status": "ok", "service": "AURa Virtual Server", "time": utcnow()})

        elif path == "/dashboard":
            self._send_html(_DASHBOARD_HTML)

        elif path == "/api/v1/status":
            self._send_json(200, aios.status() if aios else {"error": "AI OS not attached"})

        elif path == "/api/v1/metrics":
            self._send_json(200, aios.metrics() if aios else {"error": "AI OS not attached"})

        elif path == "/api/v1/cloud":
            self._send_json(200, aios.cloud.metrics() if aios else {})

        elif path == "/api/v1/cpu":
            self._send_json(200, aios.cpu.metrics() if aios else {})

        elif path == "/api/v1/models":
            self._send_json(200, {"models": aios.cloud.list_models() if aios else []})

        elif path == "/api/v1/tasks":
            self._send_json(200, {"tasks": aios.cpu.list_tasks() if aios else []})

        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        aios = self.__class__.aios
        body = self._read_json_body()

        if path == "/api/v1/ask":
            prompt = body.get("prompt", "")
            if not prompt:
                self._send_json(400, {"error": "prompt field required"})
                return
            if aios:
                resp = aios.ai_engine.ask(prompt)
                self._send_json(200, {
                    "response": resp.text,
                    "model": resp.model,
                    "tokens_used": resp.tokens_used,
                    "latency_ms": resp.latency_ms,
                })
            else:
                self._send_json(503, {"error": "AI OS not ready"})

        elif path == "/api/v1/task":
            name = body.get("name", "api_task")
            # Accept an optional numeric 'duration_ms' to simulate a workload.
            # Using a predefined task avoids executing arbitrary user-supplied code.
            try:
                duration_ms = float(body.get("duration_ms", 0))
                duration_ms = min(max(duration_ms, 0), 30_000)  # clamp 0–30 s
            except (TypeError, ValueError):
                duration_ms = 0
            if aios:
                import time as _time
                def _run(dur=duration_ms):
                    if dur > 0:
                        _time.sleep(dur / 1000.0)
                    return {"name": name, "duration_ms": dur}
                task_id = aios.cpu.submit(_run, name=name)
                self._send_json(202, {"task_id": task_id, "status": "queued"})
            else:
                self._send_json(503, {"error": "AI OS not ready"})

        else:
            self._send_json(404, {"error": "Not found"})


# ---------------------------------------------------------------------------
# VirtualServer
# ---------------------------------------------------------------------------

class VirtualServer:
    """
    AURa Virtual Server.
    Manages an HTTP server thread and exposes the REST API + dashboard.
    """

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[float] = None
        self._request_count = 0
        self._logger = get_logger("aura.server")

    def start(self, aios: "AIOS") -> None:
        _AURaHandler.aios = aios
        self._httpd = HTTPServer((self._config.host, self._config.port), _AURaHandler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="aura-server",
            daemon=True,
        )
        self._start_time = time.monotonic()
        self._thread.start()
        self._logger.info(
            "Virtual Server listening on http://%s:%d  (dashboard: /dashboard)",
            self._config.host,
            self._config.port,
        )
        EVENT_BUS.publish("server.started", {"port": self._config.port})

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
        self._logger.info("Virtual Server stopped")
        EVENT_BUS.publish("server.stopped", {})

    def metrics(self) -> dict:
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0
        return {
            "host": self._config.host,
            "port": self._config.port,
            "workers": self._config.workers,
            "uptime_seconds": round(uptime, 1),
            "running": self._thread is not None and self._thread.is_alive(),
        }
