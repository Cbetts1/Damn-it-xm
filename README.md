# AURa — Autonomous Universal Resource Architecture

> **AI-first virtual system** · Free & Open Source · v1.0.0 · Python 3.9+

![AURa Command Center Dashboard](https://github.com/user-attachments/assets/32a944d2-8ac8-4b53-8c10-eddc05c0de3d)

---

## What Is AURa?

**AURa is an AI virtual operating system.** The AI engine is the only physical
component; everything else — the cloud, the CPU, the server, the storage — is
virtual and managed by the AI OS. AURa is the bridge that harnesses virtual
compute and cloud power on demand, all governed by a single AI brain.

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

---

## ✅ Validation Report

**Tested on:** Python 3.12.3 · Linux · 2026-04-08

```
32 tests PASSED in 4.4 s
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

Run validation yourself:

```bash
pip install pytest
python -m pytest tests/test_aura.py -v
```

**Live smoke test:**

```
$ python main.py status
AURa v1.0.0  |  Uptime: 00h 00m 00s
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

```bash
git clone https://github.com/Cbetts1/Damn-it-xm
cd Damn-it-xm

# No external dependencies required
python main.py shell          # interactive shell
python main.py status         # one-shot status check
python main.py ask "hello"    # talk to the AI engine
python main.py server         # start API + web dashboard
python main.py monitor        # TUI live monitor

# Open the Command Center in your browser:
# http://localhost:8000/dashboard
```

Or install as a package:

```bash
pip install -e .
aura shell
aura ask "What can you do?"
aura server
```

---

## 🔋 Current Capabilities (v1.0.0)

### AI OS & Orchestration
- Boots and manages all virtual components in order (AI Engine → Cloud → CPU → Server)
- Unified `dispatch()` command API used by both the Shell and the REST API
- In-process `EventBus` — all subsystems publish and subscribe to events for observability
- Graceful `SIGINT`/`SIGTERM` shutdown of all threads
- Fully configurable via environment variables (no hardcoded values)
- Works on any platform with Python 3.9+

### AI Engine (the brain)
- **Built-in backend** — zero external dependencies; works 100% offline; deterministic
  rule-based responses for all system commands
- **Hugging Face Transformers backend** — load any open-source model from
  HuggingFace Hub (DialoGPT, Mistral 7B, Falcon, Llama 2, …) with a single env var
- **OpenAI-compatible backend** — connect to any local server (Ollama, LM Studio,
  text-generation-webui) with `AURA_API_BASE_URL`
- Conversation history tracking per session
- `ask()` — free-form query
- `plan_task()` — AI-generated step-by-step execution plan
- `analyse_metrics()` — AI analysis and recommendations from live metrics

### Virtual Cloud
- 8 virtual compute nodes (configurable), each with vCPUs + memory tracking
- Dynamic node add / remove
- Storage volume lifecycle: create, attach, delete (backed by local filesystem)
- AI model registry — register, list, and track large models stored in cloud cache
- Per-node CPU and memory utilisation metrics
- CDN-mode flag

### Virtual CPU
- 64 virtual cores (configurable), 128 threads, 4.2 GHz clock (configurable)
- Priority task queue with 5 levels: CRITICAL → HIGH → NORMAL → LOW → BACKGROUND
- Up to 256 concurrent tasks
- Task lifecycle tracking: QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED
- Per-task timing, error capture, and result storage
- Throughput (tasks/s) and queue-depth metrics

### Virtual Server
- Stdlib HTTP server — no FastAPI/uvicorn required
- Full REST API: health, status, metrics, ask, cloud, cpu, models, tasks
- Auto-refreshing single-page **web Command Center** at `/dashboard`
  - Live AI OS, Virtual Cloud, and Virtual CPU cards
  - Embedded AI chat panel (talks directly to the AI engine)
  - Progress bars for CPU and memory utilisation
  - No JavaScript framework required — plain JS + CSS
- CORS headers on all responses
- Graceful start/stop in its own daemon thread

### Command Center
- **Web dashboard** at `http://localhost:8000/dashboard` (auto-refreshes every 3 s)
- **TUI monitor** (`python main.py monitor`) — terminal live view, no browser needed
  - Colour-coded component status
  - ASCII progress bars for cloud utilisation

### Shell (REPL)
- Full readline integration — arrow-key history across sessions
- Tab-completion for all built-in commands
- Colour prompt and ANSI-formatted output
- Long-line wrapping that preserves ASCII art / table layouts
- All unrecognised input is routed to the AI engine automatically
- Commands: `status`, `metrics`, `cloud`, `cpu`, `server`, `nodes`, `models`,
  `tasks`, `ask`, `plan`, `analyse`, `history`, `clear_history`, `version`, `help`

---

## 🚧 What AURa Cannot Do Yet (Known Limitations)

| Limitation | Planned |
|---|---|
| Virtual CPU cannot execute real compute kernels (GPU, WASM, etc.) | Year 2 |
| Virtual Cloud does not replicate data across real network nodes | Year 2 |
| Built-in AI backend answers are rule-based (not true generative AI) | Solved by switching backend |
| No user authentication on the web dashboard | Year 1 |
| No persistent state across restarts (all in-memory) | Year 1–2 |
| No multi-user or multi-tenant support | Year 2–3 |
| No voice/speech interface | Year 3 |
| No mobile dashboard | Year 2 |

---

## 🔭 5-Year Capability Progression

### Year 1 (2026) — Foundation Hardening
- **Persistent state** — save cloud nodes, volumes, task history, and conversation
  history to SQLite so nothing is lost on restart
- **Dashboard auth** — username/password or API-key protection for the web UI
- **Plugin system** — drop a `.py` file into `~/.aura/plugins/` to add new shell
  commands and API endpoints
- **Streaming responses** — real-time token-by-token streaming in shell and dashboard
  for Transformers and OpenAI-compatible backends
- **Windows support** — verified installer and `aura shell` on Windows PowerShell

### Year 2 (2027) — Real Compute & Networking
- **Distributed Virtual Cloud** — AURa nodes discover each other over LAN/VPN;
  workloads can be offloaded to other AURa instances
- **Real GPU scheduling** — Virtual CPU tasks can request a GPU slice; the AI OS
  routes to CUDA/ROCm/Metal via a resource-pool manager
- **Model fine-tuning pipeline** — trigger LoRA fine-tuning jobs on the virtual CPU;
  trained adapters stored in the virtual cloud
- **Mobile dashboard** — responsive PWA that works on iOS and Android
- **Webhook & event triggers** — subscribe external systems to AURa events
  (e.g., Slack notification when a task fails)

### Year 3 (2028) — Autonomous Agent Layer
- **Autonomous agent mode** — the AI OS can break a high-level goal into sub-tasks,
  schedule them on the virtual CPU, and report results without human intervention
- **Multi-agent collaboration** — multiple AURa instances communicate via a shared
  message bus to cooperate on large tasks
- **Voice interface** — whisper-based speech-to-text and TTS so you can speak to AURa
- **Code interpreter** — safe sandboxed Python execution inside the virtual CPU
  (containers + seccomp) for the `/api/v1/task` endpoint
- **Long-term memory** — vector-database-backed memory so AURa remembers past
  conversations and learned facts across sessions

### Year 4 (2029) — Ecosystem & Integration
- **Marketplace** — community-contributed AI skills, plugins, and model configs
  installable with `aura install <skill>`
- **Kubernetes bridge** — the Virtual Cloud can provision real Kubernetes pods
  when available, with graceful fallback to virtual nodes
- **Multi-modal AI** — image, audio, and document understanding via pluggable
  vision and audio backends
- **Enterprise SSO** — LDAP/OIDC authentication for multi-user deployments
- **AURa SDK** — publish a Python SDK so third-party apps can embed AURa as a
  library and expose AURa capabilities via their own UI

### Year 5 (2030) — Fully Autonomous Infrastructure
- **Self-optimising resource manager** — the AI OS continuously monitors metrics
  and autonomously scales virtual nodes, adjusts CPU priority, and swaps AI models
  based on workload patterns — no human intervention required
- **Self-healing** — detect and automatically recover from failed components,
  corrupted volumes, or stalled tasks
- **Federated AURa network** — opt-in federated learning across AURa nodes:
  contribute compute, share model improvements, earn credits
- **Natural language infrastructure** — provision, configure, and manage the entire
  AURa stack using plain English from the shell or dashboard
  ("add 4 cloud nodes and run a Mistral inference benchmark")
- **AURa OS image** — bootable Linux-based OS image with AURa as the primary
  shell and interface, designed for dedicated AI appliance hardware

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

### Connecting a Free Open-Source Large Model

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

## Testing

```bash
pip install pytest
python -m pytest tests/test_aura.py -v
# 32 passed ✅
```

---

## Project Structure

```
Damn-it-xm/
├── main.py                        # Top-level entry point (delegates to aura/main.py)
├── setup.py                       # pip-installable package definition
├── requirements.txt               # Optional dependency notes
├── aura/
│   ├── __init__.py                # Package metadata
│   ├── __main__.py                # python -m aura entry point
│   ├── main.py                    # CLI dispatcher (shell/server/monitor/status/ask)
│   ├── config.py                  # All configuration dataclasses + env loading
│   ├── utils/__init__.py          # Logging, IDs, formatting, EventBus
│   ├── ai_engine/
│   │   └── engine.py              # AIEngine + backends (builtin/transformers/openai_compat)
│   ├── cloud/
│   │   └── virtual_cloud.py       # VirtualCloud: nodes, volumes, model registry
│   ├── cpu/
│   │   └── virtual_cpu.py         # VirtualCPU: priority task scheduler
│   ├── server/
│   │   └── virtual_server.py      # VirtualServer: HTTP API + web dashboard
│   ├── os_core/
│   │   └── ai_os.py               # AIOS: central orchestrator and bridge
│   ├── command_center/
│   │   └── monitor.py             # TUI live monitor
│   └── shell/
│       └── shell.py               # Interactive REPL
└── tests/
    └── test_aura.py               # 32 tests covering all components
```

---

## License

MIT — free and open source.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       AURa AI OS                        │
│          (the only physical component — the brain)      │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ Virtual     │  │ Virtual CPU │  │ Virtual Server  │ │
│  │ Cloud       │  │ 64 vCores   │  │ REST API +      │ │
│  │ 8 nodes     │  │ 4.2 GHz     │  │ Dashboard       │ │
│  │ Model cache │  │ Task queue  │  │ /dashboard      │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  AI Engine  (pluggable — free open-source)      │    │
│  │  • Built-in (zero deps, works offline)          │    │
│  │  • Hugging Face Transformers (any HF model)     │    │
│  │  • OpenAI-compatible API (Ollama, LM Studio…)   │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
  AURa Shell (CLI REPL)     Command Center (Web Dashboard)
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

---

## Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/Cbetts1/Damn-it-xm
cd Damn-it-xm

# No external dependencies needed for the built-in AI backend
python main.py shell          # interactive shell
python main.py status         # one-shot status
python main.py ask "hello"    # ask the AI directly
python main.py server         # API + dashboard only
python main.py monitor        # TUI live monitor
```

Or install as a package:

```bash
pip install -e .
aura shell
aura status
aura ask "What is AURa?"
```

Open the **Command Center** in your browser:

```
http://localhost:8000/dashboard
```

---

## AI Backend Configuration

AURa ships with a zero-dependency built-in backend. Swap to a more powerful
free open-source model with a single environment variable:

### Hugging Face Transformers (free, local)

```bash
pip install transformers torch
export AURA_AI_BACKEND=transformers
export AURA_MODEL_NAME=microsoft/DialoGPT-medium   # ~350 MB
# or
export AURA_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3  # ~14 GB
python main.py shell
```

### Ollama / LM Studio / any OpenAI-compatible server

```bash
# Start Ollama (free & open-source): https://ollama.ai
ollama run mistral

# Point AURa at it
export AURA_AI_BACKEND=openai_compatible
export AURA_API_BASE_URL=http://localhost:11434/v1
export AURA_MODEL_NAME=mistral
python main.py shell
```

---

## Shell Commands

```
status        — system health overview
metrics       — detailed component metrics
cloud         — virtual cloud metrics
cpu           — virtual CPU metrics
server        — virtual server info
nodes         — list cloud compute nodes
models        — list registered AI models
tasks         — list CPU tasks
ask <query>   — query the AI engine
plan <task>   — AI-generated task execution plan
analyse       — AI analysis of current metrics
history       — show conversation history
clear_history — clear conversation history
version       — show AURa version
help          — show this help
exit / quit   — exit the AURa shell
```

---

## REST API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/status` | Full system status |
| GET | `/api/v1/metrics` | All component metrics |
| POST | `/api/v1/ask` | `{"prompt": "…"}` → AI response |
| GET | `/api/v1/cloud` | Virtual Cloud metrics |
| GET | `/api/v1/cpu` | Virtual CPU metrics |
| GET | `/api/v1/models` | Registered AI models |
| GET | `/api/v1/tasks` | CPU task list |
| GET | `/dashboard` | Web Command Center |

---

## Configuration

All settings can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `AURA_AI_BACKEND` | `builtin` | `builtin` / `transformers` / `openai_compatible` |
| `AURA_MODEL_NAME` | `aura-assistant` | HuggingFace model ID or local model name |
| `AURA_DEVICE` | `cpu` | `cpu` / `cuda` / `mps` |
| `AURA_API_BASE_URL` | — | Base URL for OpenAI-compatible API |
| `AURA_API_KEY` | — | API key (if required) |
| `AURA_SERVER_PORT` | `8000` | Virtual Server port |
| `AURA_DASHBOARD_PORT` | `7860` | Command Center port |
| `AURA_LOG_LEVEL` | `INFO` | Logging level |
| `AURA_DATA_DIR` | `~/.aura` | Data/cache directory |

---

## Testing

```bash
pip install pytest
pytest tests/ -v
```

32 tests covering config, utils, AI engine, Virtual Cloud, Virtual CPU,
Virtual Server, AI OS orchestration, and shell dispatch.

---

## License

MIT — free and open source.
