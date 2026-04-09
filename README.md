# AURa — Autonomous Universal Resource Architecture

> **AI-first virtual system** · Free & Open Source · Python 3.9+

[![Version](https://img.shields.io/badge/version-1.2.0-blue?style=flat-square)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-yellow?style=flat-square)](https://www.python.org)
[![Termux](https://img.shields.io/badge/Termux-compatible-orange?style=flat-square)](https://termux.dev)
[![Tests](https://img.shields.io/badge/tests-98%20passed-brightgreen?style=flat-square)](tests/test_aura.py)

![AURa Command Center Dashboard](https://github.com/user-attachments/assets/32a944d2-8ac8-4b53-8c10-eddc05c0de3d)

---

## What Is AURa?

**AURa is an AI virtual operating system.**  The AI engine is the only
physical component; everything else — the cloud, the CPU, the server, the
storage — is virtual and managed by the AI OS.  AURa bridges virtual compute
and cloud power on demand, all governed by a single AI brain.

| ✅ AURa IS | ❌ AURa Is NOT |
|---|---|
| An AI OS that orchestrates virtual infrastructure | A replacement for your host OS (Linux/Windows/macOS) |
| A self-contained AI virtual system you can run locally | A cloud provider (AWS/GCP/Azure) |
| A pluggable AI inference engine (offline capable) | A pre-trained large language model |
| A REST API + live web dashboard for all components | A web browser or GUI application framework |
| A full interactive CLI shell with tab-completion | A container runtime (Docker/Kubernetes) |
| A virtual compute task scheduler (virtual CPU) | A real hypervisor or bare-metal virtualisation |
| A virtual storage and model registry (virtual cloud) | A database or persistent data store |
| Free, open-source, and works with zero dependencies | A paid or proprietary AI service |
| Extensible to plug in any HuggingFace or Ollama model | A finished end-user consumer product (it is a platform) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       AURa AI OS                            │
│         (the only physical component — the brain)           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ Virtual      │  │ Virtual CPU  │  │ Virtual Server    │ │
│  │ Cloud        │  │ 64 vCores    │  │ REST API          │ │
│  │ 8 nodes      │  │ 4.2 GHz      │  │ Web Dashboard     │ │
│  │ 1 TB storage │  │ Task queue   │  │ /dashboard        │ │
│  │ Model cache  │  │ 256 threads  │  │ /api/v1/*         │ │
│  └──────────────┘  └──────────────┘  └───────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  AI Engine  (pluggable — all free & open-source)      │  │
│  │  • builtin       : zero deps, works 100% offline      │  │
│  │  • transformers  : any Hugging Face model             │  │
│  │  • openai_compat : Ollama, LM Studio, text-gen-webui  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         ▲                                ▲
         │                                │
  AURa Shell (CLI REPL)      Command Center (Web + TUI)
```

| Component | Description |
|---|---|
| **AI OS** | Central orchestrator; boots and manages all virtual components |
| **Virtual Cloud** | Distributed compute nodes, storage volumes, model registry |
| **Virtual CPU** | Priority task scheduler backed by a thread pool |
| **Virtual Server** | HTTP API + auto-refreshing web dashboard |
| **AI Engine** | Pluggable inference: builtin → Transformers → OpenAI-compatible |
| **Command Center** | Web dashboard (`/dashboard`) + TUI live monitor |
| **Shell** | Interactive REPL with tab-completion and readline history |
| **Persistence Engine** | SQLite-backed conversation and KV store |
| **Plugin Manager** | Drop-in plugins that extend shell commands and API routes |
| **Android Bridge** | Detects Termux/Android capabilities for cross-platform support |

---

## ✅ Validation Report — v1.2.0

**Tested on:** Python 3.12.3 · Linux · 2026-04-09

```
98 tests PASSED in 17.3 s
```

| Test Area | Tests | Result |
|---|---|---|
| Configuration & env overrides | 2 | ✅ PASS |
| Utility helpers (IDs, formatting, EventBus) | 5 | ✅ PASS |
| AI Engine — builtin backend | 3 | ✅ PASS |
| AI Engine — high-level API | 4 | ✅ PASS |
| Virtual Cloud (nodes, volumes, models, metrics) | 5 | ✅ PASS |
| Virtual CPU (lifecycle, tasks, failures, metrics) | 4 | ✅ PASS |
| Virtual Server — HTTP integration | 3 | ✅ PASS |
| AI OS — orchestration & shell dispatch | 6 | ✅ PASS |
| Persistence Engine (SQLite KV + history) | 14 | ✅ PASS |
| Plugin Manager (register/dispatch/unregister) | 5 | ✅ PASS |
| Menu / Workspace rendering | 2 | ✅ PASS |
| Shell executor (pwd, echo, cd, ls, cat, wc, …) | 14 | ✅ PASS |
| Android/Termux bridge (platform detection) | 31 | ✅ PASS |

Run validation yourself:

```bash
pip install pytest
python -m pytest tests/test_aura.py -v
```

**Live smoke test:**

```
$ python main.py status
AURa v1.2.0  |  Uptime: 00h 00m 00s
  ✅  ai_os                  online
  ✅  ai_engine              ready
  ✅  virtual_cloud          online
  ✅  virtual_cpu            running
  ✅  virtual_server         running

$ python main.py ask "hello"
Hello! I'm AURa, your AI OS. How can I assist you today?

$ python main.py ask "status"
All AURa virtual components are operational.
  • AI OS     : Running
  • Virtual Cloud : Online  (8 nodes)
  • Virtual CPU   : Active  (64 vCores @ 4.2 GHz)
  • Virtual Server: Serving (port 8000)
```

---

## Quick Start

### Linux / macOS / WSL

```bash
git clone https://github.com/Cbetts1/Damn-it-xm
cd Damn-it-xm

# No external dependencies required
python main.py shell          # interactive shell
python main.py status         # one-shot status check
python main.py ask "hello"    # talk to the AI engine
python main.py server         # start API + web dashboard
python main.py monitor        # TUI live monitor
```

Or install as a package:

```bash
pip install -e .
aura shell
aura ask "What can you do?"
aura server
```

Open the **Command Center** in your browser:
```
http://localhost:8000/dashboard
```

### 📱 Termux / Android (One-Command Install)

AURa runs fully on Android via [Termux](https://termux.dev) — no root required.

```bash
# 1. Install Termux from F-Droid: https://f-droid.org/packages/com.termux/
# 2. Open Termux and run:
pkg update -y && pkg install -y python git
git clone https://github.com/Cbetts1/Damn-it-xm
cd Damn-it-xm
bash upgrade.sh        # installs pytest & validates everything
python main.py shell   # start the AURa shell
```

**Termux one-liner (after installing python + git):**

```bash
git clone https://github.com/Cbetts1/Damn-it-xm && cd Damn-it-xm && bash upgrade.sh
```

> **Note:** AURa uses only Python stdlib + optional lightweight extras — no
> native compiler or heavy packages required on mobile.

---

## 🔋 Capabilities (v1.2.0)

### AI OS & Orchestration
- Boots and manages all virtual components in order (AI Engine → Cloud → CPU → Server)
- Unified `dispatch()` command API used by the Shell and REST API
- In-process `EventBus` — all subsystems publish and subscribe to events
- Graceful `SIGINT`/`SIGTERM` shutdown of all threads
- Fully configurable via environment variables (no hardcoded values)
- Works on any platform with Python 3.9+ including Android/Termux

### AI Engine (the brain)
- **Built-in backend** — zero external dependencies; 100% offline; deterministic
- **Hugging Face Transformers backend** — any open-source model (DialoGPT, Mistral 7B, …)
- **OpenAI-compatible backend** — Ollama, LM Studio, text-generation-webui
- Conversation history tracking with bounded in-memory buffer (500 entries max)
- `ask()` — free-form query; `plan_task()` — step-by-step plans; `analyse_metrics()` — AI recommendations

### Virtual Cloud
- 8 virtual compute nodes (configurable), vCPUs + memory metrics
- Dynamic node add / remove
- Storage volume lifecycle: create, attach, delete
- AI model registry — register, list, and track large model files
- CDN-mode flag; per-node metrics

### Virtual CPU
- 64 virtual cores, 128 threads, 4.2 GHz (all configurable)
- Priority task queue with 5 levels: CRITICAL → HIGH → NORMAL → LOW → BACKGROUND
- Up to 256 concurrent tasks
- Task lifecycle: QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED
- Throughput and queue-depth metrics

### Virtual Server
- Stdlib HTTP server — no FastAPI/uvicorn required
- Full REST API: health, status, metrics, ask, cloud, cpu, models, tasks
- Auto-refreshing single-page **web Command Center** at `/dashboard`
- CORS headers on all responses

### Shell (REPL)
- Full readline integration — arrow-key history across sessions
- Tab-completion for all built-in commands
- Colour prompt and ANSI-formatted output
- `!<cmd>` shorthand to execute shell commands (pwd, ls, echo, cd, …)
- All unrecognised input routed to the AI engine automatically

### Persistence Engine
- SQLite-backed key-value store and conversation history
- Retry-safe writes; survives process restart
- History loaded back into the AI engine on startup

### Plugin Manager
- Register plugins that extend shell commands and API routes
- `PluginManager.dispatch()` routes to the right plugin
- Duplicate registration raises an error

### Android / Termux Bridge
- `detect_capabilities()` returns platform facts (Python version, Termux flag, available tools)
- `AndroidBridge.subprocess_run()` — safe cross-platform subprocess execution
- Powers the shell executor (`pwd`, `echo`, `ls`, `mkdir`, `touch`, `cat`, `wc`, `date`, `uname`, `which`, `df`)

---

## Shell Commands

```
status        — full system health (all components)
metrics       — detailed live metrics (cloud + cpu + server)
cloud         — virtual cloud status and node list
cpu           — virtual CPU metrics and task stats
server        — virtual server info and URLs
nodes         — list all cloud compute nodes
models        — list AI models registered in the cloud
tasks         — list recent CPU task history
ask <query>   — send a query directly to the AI engine
plan <task>   — AI-generated step-by-step execution plan
analyse       — AI analysis + recommendations for current metrics
history       — show conversation history
clear_history — clear conversation history
version       — show AURa version
help          — show this help
exit / quit   — exit the AURa shell
! <cmd>       — run a shell command (ls, pwd, echo, cd, …)
```

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check — always returns `{"status":"ok"}` |
| GET | `/api/v1/status` | Full system status snapshot |
| GET | `/api/v1/metrics` | Live metrics for all components |
| POST | `/api/v1/ask` | `{"prompt":"…"}` → AI engine response |
| GET | `/api/v1/cloud` | Virtual Cloud metrics |
| GET | `/api/v1/cpu` | Virtual CPU metrics |
| GET | `/api/v1/models` | Registered AI models in cloud |
| GET | `/api/v1/tasks` | CPU task list |
| POST | `/api/v1/task` | `{"name":"…","duration_ms":0}` → submit task |
| GET | `/dashboard` | Web Command Center (single-page app) |

---

## AI Backend Configuration

| Variable | Default | Description |
|---|---|---|
| `AURA_AI_BACKEND` | `builtin` | `builtin` / `transformers` / `openai_compatible` |
| `AURA_MODEL_NAME` | `aura-assistant` | HuggingFace model ID or Ollama model name |
| `AURA_DEVICE` | `cpu` | `cpu` / `cuda` / `mps` |
| `AURA_API_BASE_URL` | — | Base URL for OpenAI-compatible API |
| `AURA_API_KEY` | — | API key if required by the server |
| `AURA_SERVER_PORT` | `8000` | Virtual Server HTTP port |
| `AURA_DASHBOARD_PORT` | `7860` | Command Center port |
| `AURA_LOG_LEVEL` | `INFO` | Log level: DEBUG / INFO / WARNING / ERROR |
| `AURA_DATA_DIR` | `~/.aura` | Data and model cache directory |

### Connect a Free Open-Source Large Model

```bash
# Option A — Hugging Face (downloads model locally, ~14 GB for Mistral 7B)
pip install transformers torch
export AURA_AI_BACKEND=transformers
export AURA_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3
python main.py shell

# Option B — Ollama (run a local server, then point AURa at it)
# Install Ollama: https://ollama.ai
ollama run mistral        # starts server on localhost:11434
export AURA_AI_BACKEND=openai_compatible
export AURA_API_BASE_URL=http://localhost:11434/v1
export AURA_MODEL_NAME=mistral
python main.py shell
```

---

## Project Structure

```
Damn-it-xm/
├── main.py                        # Top-level entry point
├── setup.py                       # pip-installable package definition
├── requirements.txt               # Optional dependency notes
├── upgrade.sh                     # One-command Termux / Linux upgrade script
├── LICENSE                        # MIT License
├── CHANGELOG.md                   # Version history
├── TERMS_OF_USE.md                # Terms of Use
├── PRIVACY_NOTICE.md              # Privacy Notice
├── DISCLAIMER.md                  # Warranty Disclaimer
└── aura/
    ├── __init__.py                # Package metadata (version 1.2.0)
    ├── __main__.py                # python -m aura entry point
    ├── main.py                    # CLI dispatcher (shell/server/monitor/status/ask)
    ├── config.py                  # All configuration dataclasses + env loading
    ├── utils/__init__.py          # Logging, IDs, formatting, EventBus
    ├── ai_engine/engine.py        # AIEngine + backends (builtin/transformers/openai_compat)
    ├── cloud/virtual_cloud.py     # VirtualCloud: nodes, volumes, model registry
    ├── cpu/virtual_cpu.py         # VirtualCPU: priority task scheduler
    ├── server/virtual_server.py   # VirtualServer: HTTP API + web dashboard
    ├── os_core/ai_os.py           # AIOS: central orchestrator and bridge
    ├── persistence/store.py       # SQLite persistence engine
    ├── plugins/manager.py         # Plugin manager
    ├── adapters/android_bridge.py # Termux / Android cross-platform bridge
    ├── command_center/monitor.py  # TUI live monitor
    └── shell/
        ├── shell.py               # Interactive REPL
        └── commands.py            # Built-in shell command executor
└── tests/
    └── test_aura.py               # 98 tests covering all components
```

---

## 🚧 Known Limitations

| Limitation | Planned |
|---|---|
| Virtual CPU cannot execute real compute kernels (GPU, WASM, etc.) | Year 2 |
| Virtual Cloud does not replicate data across real network nodes | Year 2 |
| Built-in AI backend answers are rule-based (not true generative AI) | Solved by switching backend |
| No user authentication on the web dashboard | Year 1 |
| No multi-user or multi-tenant support | Year 2–3 |
| No voice/speech interface | Year 3 |
| No mobile-optimised dashboard | Year 2 |

---

## 🔭 5-Year Capability Progression

### Year 1 (2026) — Foundation Hardening
- Dashboard auth — API-key protection for the web UI
- Plugin system — drop a `.py` into `~/.aura/plugins/`
- Streaming responses — real-time token-by-token in shell and dashboard
- Windows PowerShell support

### Year 2 (2027) — Real Compute & Networking
- Distributed Virtual Cloud — AURa nodes discover each other over LAN/VPN
- Real GPU scheduling — CUDA/ROCm/Metal resource-pool manager
- Model fine-tuning pipeline — LoRA jobs on the virtual CPU
- Mobile-responsive PWA dashboard

### Year 3 (2028) — Autonomous Agent Layer
- Autonomous agent mode — break goals into sub-tasks automatically
- Multi-agent collaboration — AURa instances cooperate via message bus
- Voice interface — Whisper speech-to-text + TTS
- Safe sandboxed Python interpreter inside virtual CPU tasks

### Year 4 (2029) — Ecosystem & Integration
- Community marketplace — `aura install <skill>`
- Kubernetes bridge — provision real pods when available
- Multi-modal AI — image, audio, document understanding
- Enterprise SSO — LDAP/OIDC authentication

### Year 5 (2030) — Fully Autonomous Infrastructure
- Self-optimising resource manager — scales and adjusts with no human input
- Self-healing — automatic recovery from failed components
- Federated AURa network — opt-in learning and compute sharing
- Natural language infrastructure provisioning
- AURa OS image — bootable Linux with AURa as the primary shell

---

## ⚖️ Legal

### License

AURa is released under the **MIT License**.  See [`LICENSE`](LICENSE) for the
full text.

```
Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

### Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
All "Virtual" components are **pure software simulations** and are not
physical devices or production infrastructure.  See [`DISCLAIMER.md`](DISCLAIMER.md).

### Privacy

AURa stores data **locally only** in `~/.aura/`.  No telemetry or analytics
are collected.  See [`PRIVACY_NOTICE.md`](PRIVACY_NOTICE.md).

### Terms of Use

By using AURa you agree to the [`TERMS_OF_USE.md`](TERMS_OF_USE.md).

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes; add or update tests.
4. Run `python -m pytest tests/test_aura.py -v` — all tests must pass.
5. Open a pull request against `main`.

All contributions are subject to the MIT License and the
[GitHub Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service).

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for a full version history.

---

*AURa v1.2.0 · Free & Open Source · Built with ❤️ by the AURa Project*
