# AURa — Autonomous Universal Resource Architecture

> **AI-first virtual operating system** · v2.0.0

[![Version](https://img.shields.io/badge/version-2.0.0-blue?style=flat-square)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-yellow?style=flat-square)](https://www.python.org)
[![Termux](https://img.shields.io/badge/Termux-compatible-orange?style=flat-square)](https://termux.dev)
[![Tests](https://img.shields.io/badge/tests-337%20passed-brightgreen?style=flat-square)](tests/test_aura.py)

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
┌─────────────────────────────────────────────────────────────────┐
│                        AURa AI OS  v2.0.0                       │
│           (the only physical component — the brain)             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ Virtual      │  │ Virtual CPU  │  │ Virtual Server      │   │
│  │ Cloud        │  │ 64 vCores    │  │ REST API            │   │
│  │ 8 nodes      │  │ 4.2 GHz      │  │ Web Dashboard       │   │
│  │ 1 TB storage │  │ Task queue   │  │ /dashboard          │   │
│  │ Model cache  │  │ 256 threads  │  │ /api/v1/*           │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  AI Engine  (pluggable — all free & open-source)        │    │
│  │  • builtin       : zero deps, works 100% offline        │    │
│  │  • transformers  : any Hugging Face model               │    │
│  │  • openai_compat : Ollama, LM Studio, text-gen-webui    │    │
│  │  • Cloud AI Router: routes llama3.1:8b via VirtualCPU   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Kernel Services    │  │ Filesystem Layer                 │   │
│  │ ProcessManager     │  │ VirtualFileSystem (VFS)          │   │
│  │ IPCBus             │  │ ProcFS (/proc/aura/*)            │   │
│  │ SyslogService      │  │ FHSMapper                        │   │
│  │ SecretsManager     │  └──────────────────────────────────┘   │
│  │ CronService        │  ┌──────────────────────────────────┐   │
│  │ ServiceManager     │  │ Identity & Governance            │   │
│  └────────────────────┘  │ CryptoIdentityEngine             │   │
│  ┌────────────────────┐  │ IdentityRegistry                 │   │
│  │ Hardware /dev/*    │  │ AuditLog                         │   │
│  │ /dev/vcpu  /vram   │  └──────────────────────────────────┘   │
│  │ /dev/vdisk /vnet   │  ┌──────────────────────────────────┐   │
│  │ /dev/vbt   /vgpu   │  │ Package Manager                  │   │
│  └────────────────────┘  │ PackageRegistry + Installer      │   │
│  ┌────────────────────┐  └──────────────────────────────────┘   │
│  │ ROOT Sovereign     │  ┌──────────────────────────────────┐   │
│  │ DeviceManager      │  │ Web/Remote Layer                 │   │
│  │ HOME Userland      │  │ WebAPI + WebSocketHub            │   │
│  │ BuildPipeline      │  └──────────────────────────────────┘   │
│  └────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────┘
          ▲                                 ▲
          │                                 │
   AURa Shell (CLI REPL)       Command Center (Web + TUI)
```

| Component | Description |
|---|---|
| **AI OS** | Central orchestrator; boots all virtual components in order |
| **Virtual Cloud** | Distributed compute nodes, storage volumes, model registry |
| **Virtual CPU** | Priority task scheduler backed by a thread pool |
| **Virtual Server** | HTTP API + auto-refreshing web dashboard |
| **AI Engine** | Pluggable inference: builtin → Transformers → OpenAI-compatible |
| **Cloud AI Router** | Routes llama3.1:8b inference through VirtualCPU + VirtualCloud |
| **Command Center** | Web dashboard (`/dashboard`) + TUI live monitor |
| **Shell** | Interactive REPL with tab-completion and readline history |
| **Kernel Services** | ProcessManager, IPCBus, SyslogService, SecretsManager, CronService, ServiceManager |
| **Filesystem Layer** | VirtualFileSystem (VFS), ProcFS, FHSMapper |
| **Hardware /dev/*** | Virtual devices: vcpu, vram, vdisk, vnet, vbt, vgpu — managed by DeviceManager |
| **ROOT Sovereign** | Deny-by-default firewall; approval gateway for all device access |
| **HOME Userland** | User-facing filesystem and process environment |
| **Build Pipeline** | Build → sign (HMAC-SHA256) → approve → deploy lifecycle |
| **Identity & Governance** | CryptoIdentityEngine, IdentityRegistry, AuditLog |
| **Package Manager** | PackageRegistry + PackageInstaller for drop-in extensions |
| **Web/Remote Layer** | WebAPI + WebSocketHub for remote control |
| **Persistence Engine** | SQLite-backed conversation and KV store |
| **Plugin Manager** | Drop-in plugins that extend shell commands and API routes |
| **Android Bridge** | Detects Termux/Android capabilities for cross-platform support |

---

## ✅ Validation Report — v2.0.0

**Tested on:** Python 3.12.3 · Linux · 2026-04-10

```
337 tests PASSED
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
| ROOT sovereign layer | — | ✅ PASS |
| Hardware /dev/* devices | — | ✅ PASS |
| Kernel services (process, ipc, syslog, cron, …) | — | ✅ PASS |
| Filesystem layer (VFS, ProcFS, FHS) | — | ✅ PASS |
| Package manager (registry + installer) | — | ✅ PASS |
| Web/remote layer (WebAPI, WebSocket) | — | ✅ PASS |
| Identity & governance (crypto, audit) | — | ✅ PASS |
| Cloud AI Router (Ollama integration) | — | ✅ PASS |
| Build pipeline (sign, approve, deploy) | — | ✅ PASS |

Run validation yourself:

```bash
pip install pytest
python -m pytest tests/test_aura.py -v
```

**Live smoke test:**

```
$ python main.py status
AURa v2.0.0  |  Uptime: 00h 00m 00s
  ✅  ai_os                  online
  ✅  ai_engine              ready
  ✅  virtual_cloud          online
  ✅  virtual_cpu            running
  ✅  virtual_server         running
  ✅  root                   online
  ✅  home                   mounted
  ✅  dev_vnet               online
  ✅  dev_vgpu               online

$ python main.py ask "hello"
Hello! I'm AURa, your AI OS. How can I assist you today?

$ python main.py ask "status"
All AURa virtual components are operational.
  • AI OS          : Running
  • Virtual Cloud  : Online  (8 nodes)
  • Virtual CPU    : Active  (64 vCores @ 4.2 GHz)
  • Virtual Server : Serving (port 8000)
  • ROOT           : Online  (deny-by-default)
  • Kernel         : Online  (6 services)
```

---

## Quick Start

### Linux / macOS / WSL

```bash
git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm

# No external dependencies required
python main.py shell          # interactive shell (default)
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
git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm
bash upgrade.sh        # installs pytest & validates everything
python main.py shell   # start the AURa shell
```

**Termux one-liner (after installing python + git):**

```bash
git clone https://github.com/Cbetts1/Damn-it-xm.git && cd Damn-it-xm && bash upgrade.sh
```

> **Note:** AURa uses only Python stdlib + optional lightweight extras — no
> native compiler or heavy packages required on mobile.

---

## 🔋 Capabilities (v2.0.0)

### AI OS & Orchestration
- 9-stage boot sequence: kernel services → filesystem → package manager → web layer → AI enhancements → ROOT → AI Engine → Cloud → CPU → Server → hardware → HOME → build pipeline → services
- Unified `dispatch()` command API used by the Shell and REST API
- In-process `EventBus` — all subsystems publish and subscribe to events
- Graceful `SIGINT`/`SIGTERM` shutdown of all threads
- Fully configurable via environment variables (no hardcoded values)
- Works on any platform with Python 3.9+ including Android/Termux

### AI Engine (the brain)
- **Built-in backend** — zero external dependencies; 100% offline; deterministic
- **Hugging Face Transformers backend** — any open-source model (DialoGPT, Mistral 7B, …)
- **OpenAI-compatible backend** — Ollama, LM Studio, text-generation-webui
- **Cloud AI Router** — routes `llama3.1:8b` inference through VirtualCPU thread pool + VirtualCloud; keeps heavy model weights out of the main Python process
- **Model Registry** — tracks AI model metadata across backends
- **Personality Kernel** — configurable AI persona and response style
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

### Kernel Services (v2.0.0)
- **ProcessManager** — tracks virtual processes (spawn, list, kill)
- **IPCBus** — inter-process communication between subsystems
- **SyslogService** — rolling system log with timestamped entries
- **SecretsManager** — encrypted in-memory secret store
- **CronService** — recurring background job scheduler
- **ServiceManager** — lifecycle management for core services

### Filesystem Layer (v2.0.0)
- **VirtualFileSystem** — POSIX-style mountable VFS with pluggable providers
- **ProcFS** — `/proc/aura/*` dynamic entries (version, uptime, etc.)
- **FHSMapper** — maps AURa virtual paths to Filesystem Hierarchy Standard layout

### Hardware /dev/* (v2.0.0)
- `/dev/vcpu` — virtual CPU device backed by VirtualCPU task scheduler
- `/dev/vram` — 32 GB virtual RAM device with metrics
- `/dev/vdisk` — virtual disk with file-backed storage
- `/dev/vnet` — virtual network stack (DHCP, DNS, NAT, firewall)
- `/dev/vbt` — virtual Bluetooth device
- `/dev/vgpu` — compute dispatcher; spills to virtual cloud when local CPU > 80%
- All devices registered through **DeviceManager** and gated by ROOT

### ROOT Sovereign Layer (v2.0.0)
- Deny-by-default firewall; every device access requires ROOT approval
- Cryptographic approval tokens (HMAC-SHA256)
- Governs HOME userland mount/unmount and all /dev/* claims
- Configurable via `AURA_ROOT_SECRET`

### Identity & Governance (v2.0.0)
- **CryptoIdentityEngine** — issues signed identity tokens (NODE, USER, SERVICE kinds)
- **IdentityRegistry** — tracks all issued identities with metadata
- **AuditLog** — tamper-evident event log flushed to disk on shutdown

### Package Manager (v2.0.0)
- **PackageRegistry** — tracks available and installed packages with metadata
- **PackageInstaller** — install, remove, and list packages; `git`-based install supported

### Web/Remote Layer (v2.0.0)
- **WebAPI** — lightweight REST API layer with optional token authentication
- **WebSocketHub** — manages up to 64 concurrent WebSocket client connections

### Shell (REPL)
- Full readline integration — arrow-key history across sessions
- Tab-completion for all built-in commands
- Colour prompt and ANSI-formatted output
- `!<cmd>` shorthand to execute host shell commands (pwd, ls, echo, cd, …)
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
── Core ─────────────────────────────────────────────────────────
status        — full system health (all components)
metrics       — detailed live metrics (cloud + cpu + server)
cloud         — virtual cloud metrics (alias for metrics)
cpu           — virtual CPU metrics and task stats
server        — virtual server info and URLs
nodes         — list all cloud compute nodes
models        — list AI models registered in the cloud
tasks         — list recent CPU task history
version       — show AURa version
help / ?      — show this help
exit / quit   — exit the AURa shell
clear         — clear the terminal screen

── AI ───────────────────────────────────────────────────────────
ask <query>         — query the built-in AI engine
cloud-ai status     — Cloud AI Router status (Ollama)
cloud-ai ask <q>    — ask the large cloud AI model (llama3.1:8b)
cloud-ai pull [m]   — download model to virtual cloud
cloud-ai models     — list models in virtual cloud
cloud-ai list       — list models on the Ollama server
plan <task>         — AI-generated step-by-step execution plan
analyse             — AI analysis + recommendations for current metrics
history             — show conversation history
clear_history       — clear conversation history
personality         — AI personality kernel status
modelreg            — AI model registry

── System ───────────────────────────────────────────────────────
platform      — detected platform capabilities (OS, Termux, arch, …)
root          — ROOT sovereign layer status
home          — HOME userland status
banner        — show AURa boot banner

── Hardware /dev/* ──────────────────────────────────────────────
dev           — list all /dev/* virtual hardware devices
net           — network stack status (DHCP / DNS / NAT / firewall)
vgpu          — compute dispatcher (/dev/vgpu) status
vram          — virtual RAM device status
vdisk         — virtual disk device status

── Kernel ───────────────────────────────────────────────────────
kernel        — kernel services overview
proc          — process manager status
syslog        — system log viewer
cron …        — cron job management (list / add / remove)
svc …         — service manager (list / start / stop)

── Filesystem ───────────────────────────────────────────────────
fs …          — HOME filesystem (ls / mkdir / write / read / rm / info)
vfs …         — virtual filesystem operations

── Packages ─────────────────────────────────────────────────────
pkg …         — package manager (list / install / remove / git)
apkg …        — AURA package manager (registry / install / list)

── Build & Deploy ───────────────────────────────────────────────
build …       — build pipeline (run / list / approve / reject)
git …         — git operations (clone / pull / status)

── Identity & Governance ────────────────────────────────────────
identity      — identity registry status
audit         — recent audit log entries

── Connectivity ─────────────────────────────────────────────────
mirror        — mirror service status
intel         — intelligence index summary

── Utilities ────────────────────────────────────────────────────
plugins       — list registered plugins
kv …          — key-value persistence store
              kv set <ns> <key> <val>
              kv get <ns> <key>
              kv del <ns> <key>
              kv list <ns>
              kv namespaces
bash <cmd>    — run a host shell command
! <cmd>       — shorthand for bash (e.g. !ls, !pwd)
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
| `AURA_API_TOKEN` | — | Token for Virtual Server API authentication |
| `AURA_OLLAMA_URL` | `http://localhost:11434` | Ollama server base URL |
| `AURA_OLLAMA_MODEL` | `llama3.1:8b` | Model name to use via Cloud AI Router |
| `AURA_ROOT_SECRET` | *(change me)* | HMAC secret for ROOT approval tokens |
| `AURA_BUILD_SECRET` | *(change me)* | HMAC secret for build artefact signing |
| `AURA_COMPUTE_BACKEND` | `local` | Compute backend: `local` / `cloud` |
| `AURA_HOME_DIR` | `~/.aura/home` | HOME userland base directory |
| `AURA_BOOT_DEVICE` | — | SD-card / external storage path to boot HOME from |

### Connect a Free Open-Source Large Model

```bash
# Option A — Hugging Face (downloads model locally, ~14 GB for Mistral 7B)
pip install transformers torch
export AURA_AI_BACKEND=transformers
export AURA_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3
python main.py shell

# Option B — Ollama (run a local server, then use the Cloud AI Router)
# Install Ollama: https://ollama.ai
ollama serve                   # start the Ollama server (localhost:11434)
ollama pull llama3.1:8b        # pull the default AURa cloud model
# AURa auto-connects — just start:
python main.py shell
# Then in the shell:
# cloud-ai status              # check Ollama connection
# cloud-ai ask "hello"         # inference routed through VirtualCPU

# Option C — Use any OpenAI-compatible server (LM Studio, text-gen-webui, etc.)
export AURA_AI_BACKEND=openai_compatible
export AURA_API_BASE_URL=http://localhost:1234/v1
export AURA_MODEL_NAME=your-model-name
python main.py shell
```

---

## Project Structure

```
Damn-it-xm/
├── main.py                        # Top-level entry point (delegates to aura/main.py)
├── setup.py                       # pip-installable package definition
├── requirements.txt               # Optional dependency notes
├── upgrade.sh                     # One-command Termux / Linux upgrade & validation
├── LICENSE                        # MIT License
├── CHANGELOG.md                   # Version history
├── TERMS_OF_USE.md                # Terms of Use
├── PRIVACY_NOTICE.md              # Privacy Notice
├── DISCLAIMER.md                  # Warranty Disclaimer
├── branding/
│   ├── banner.py                  # Boot banner generator
│   └── assets.py                  # Branding assets
└── aura/
    ├── __init__.py                # Package metadata (version 2.0.0)
    ├── __main__.py                # python -m aura entry point
    ├── main.py                    # CLI dispatcher (shell/server/monitor/status/ask)
    ├── config.py                  # All configuration dataclasses + env loading
    ├── utils/                     # Logging, IDs, formatting, EventBus
    ├── ai_engine/
    │   ├── engine.py              # AIEngine + backends (builtin/transformers/openai_compat)
    │   ├── model_registry.py      # AI model metadata registry
    │   ├── personality_kernel.py  # AI persona and response style
    │   ├── ollama_backend.py      # Ollama REST API backend
    │   └── llama_backend.py       # LLaMA-family backend helpers
    ├── cloud/
    │   ├── virtual_cloud.py       # VirtualCloud: nodes, volumes, model registry
    │   └── cloud_ai_router.py     # Routes inference through VirtualCPU + VirtualCloud
    ├── cpu/virtual_cpu.py         # VirtualCPU: priority task scheduler
    ├── server/virtual_server.py   # VirtualServer: HTTP API + web dashboard
    ├── os_core/ai_os.py           # AIOS: central orchestrator and bridge
    ├── kernel/
    │   ├── process_manager.py     # Virtual process lifecycle
    │   ├── ipc.py                 # Inter-process communication bus
    │   ├── syslog.py              # Rolling system log service
    │   ├── secrets_manager.py     # In-memory encrypted secrets
    │   ├── cron.py                # Recurring background job scheduler
    │   └── service_manager.py     # Core service lifecycle manager
    ├── fs/
    │   ├── vfs.py                 # Virtual Filesystem (POSIX-style mounts)
    │   ├── procfs.py              # /proc/aura/* dynamic entries
    │   └── fhs.py                 # Filesystem Hierarchy Standard mapper
    ├── pkg/
    │   ├── registry.py            # Package registry
    │   ├── installer.py           # Package installer (including git-based)
    │   └── metadata.py            # Package metadata model
    ├── web/
    │   ├── api.py                 # Lightweight WebAPI with optional auth
    │   └── ws.py                  # WebSocket hub (up to 64 clients)
    ├── root/sovereign.py          # ROOT sovereign layer (deny-by-default)
    ├── hardware/
    │   ├── device_manager.py      # /dev/* device registry and ROOT gating
    │   ├── vcpu.py                # /dev/vcpu — virtual CPU device
    │   ├── vram.py                # /dev/vram — virtual RAM device
    │   ├── vdisk.py               # /dev/vdisk — virtual disk device
    │   ├── vnet.py                # /dev/vnet — virtual network device
    │   ├── vbt.py                 # /dev/vbt  — virtual Bluetooth device
    │   └── vgpu.py                # /dev/vgpu — compute dispatcher
    ├── network/stack.py           # Virtual network stack (DHCP, DNS, NAT, FW)
    ├── compute/dispatcher.py      # Compute backend abstraction
    ├── boot/
    │   ├── bootloader.py          # Boot state machine
    │   └── aura_init.py           # PID-1 equivalent service manager
    ├── home/userland.py           # HOME userland filesystem and processes
    ├── build/
    │   ├── pipeline.py            # Build → sign → approve → deploy lifecycle
    │   └── signer.py              # HMAC-SHA256 artefact signing and verification
    ├── identity/
    │   ├── crypto.py              # CryptoIdentityEngine (signed tokens)
    │   └── registry.py            # IdentityRegistry
    ├── governance/audit.py        # AuditLog (tamper-evident event log)
    ├── resources/intelligence_index.py  # Intelligence index store
    ├── command_center/
    │   ├── monitor.py             # TUI live monitor
    │   └── mirror.py              # Mirror service
    ├── persistence/store.py       # SQLite persistence engine
    ├── plugins/manager.py         # Plugin manager
    ├── adapters/android_bridge.py # Termux / Android cross-platform bridge
    ├── shell/
    │   ├── shell.py               # Interactive REPL
    │   └── commands.py            # Built-in shell command executor
    ├── scheduler/                 # Task scheduling utilities
    ├── orchestration/             # Cross-component orchestration helpers
    └── metrics/                   # Metrics aggregation helpers
└── tests/
    └── test_aura.py               # 337 tests covering all components
```

---

## 🚧 Known Limitations

| Limitation | Planned |
|---|---|
| Virtual CPU cannot execute real compute kernels (GPU, WASM, etc.) | Year 2 |
| Virtual Cloud does not replicate data across real network nodes | Year 2 |
| Built-in AI backend answers are rule-based (not true generative AI) | Solved by switching backend |
| Cloud AI Router requires a running Ollama server (not bundled) | Year 1 |
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
4. Run `python -m pytest tests/test_aura.py -v` — all 337 tests must pass.
5. Open a pull request against `main`.

All contributions are subject to the MIT License and the
[GitHub Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service).

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for a full version history.

---

*AURa v2.0.0 · Free & Open Source · Built with ❤️ by the AURa Project*
