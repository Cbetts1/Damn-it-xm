# AURa — Autonomous Universal Resource Architecture

> **AI-first virtual system** · Free & Open Source · v1.0.0

![AURa Command Center](https://github.com/user-attachments/assets/32a944d2-8ac8-4b53-8c10-eddc05c0de3d)

AURa is a complete AI virtual system where the **AI is the only physical
component**. Everything else — cloud, CPU, server — is virtual and managed by
the AI OS. Large AI models live in the Virtual Cloud; the AI OS is the bridge
that harnesses their power on demand.

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
