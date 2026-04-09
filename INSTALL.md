# Installing AURa

AURa requires **Python 3.9 or higher**. It has **zero required external dependencies** — the entire core runs on the Python standard library.

---

## Quick Start (any platform)

```bash
# Clone
git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm

# (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install
pip install -e .

# Launch AURa shell
aura shell
# or
python main.py shell
```

---

## Installing on Android / Termux

AURa is fully compatible with [Termux](https://termux.dev).

```bash
# 1. Install Termux from F-Droid (recommended) or Google Play
# 2. Open Termux and run:
pkg update && pkg upgrade -y
pkg install python git -y

# 3. Clone and install AURa
git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm
pip install -e .

# 4. Start AURa
aura shell
```

AURa will automatically detect the Termux environment and enable Android-specific capabilities.

---

## Installing on Linux

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install python3 python3-pip git -y

# Arch Linux
sudo pacman -S python python-pip git

# Fedora
sudo dnf install python3 python3-pip git

# Clone and install
git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm
pip install -e .
aura shell
```

---

## Installing on Windows

```powershell
# Install Python 3.9+ from https://python.org
# Install Git from https://git-scm.com

git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm
pip install -e .
python main.py shell
```

> Note: The `bash` command in the AURa shell will use `cmd.exe` or PowerShell on Windows.

---

## Optional Backends

### Hugging Face Transformers

```bash
pip install transformers torch
export AURA_AI_BACKEND=transformers
export AURA_MODEL_NAME=gpt2
aura shell
```

### Ollama / LM Studio (OpenAI-compatible API)

```bash
# Start Ollama: ollama serve
export AURA_AI_BACKEND=openai_compatible
export AURA_API_BASE_URL=http://localhost:11434/v1
export AURA_MODEL_NAME=llama3
aura shell
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AURA_AI_BACKEND` | `builtin` | AI backend: `builtin`, `transformers`, `openai_compatible` |
| `AURA_MODEL_NAME` | `aura-assistant` | Model identifier |
| `AURA_DEVICE` | `cpu` | Compute device: `cpu`, `cuda`, `mps` |
| `AURA_API_BASE_URL` | — | Base URL for openai_compatible backend |
| `AURA_API_KEY` | — | API key for openai_compatible backend |
| `AURA_SERVER_PORT` | `8000` | HTTP server port |
| `AURA_DASHBOARD_PORT` | `7860` | Dashboard port |
| `AURA_DATA_DIR` | `~/.aura` | Data directory |
| `AURA_DB_PATH` | `~/.aura/aura.db` | Persistence database path |
| `AURA_LOG_LEVEL` | `INFO` | Log level |

---

## Verifying the Installation

```bash
# Run all tests
python -m pytest tests/test_aura.py -v

# Quick smoke test
aura status
```

Expected output: 46 tests passed.
