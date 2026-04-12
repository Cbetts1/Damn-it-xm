# AURa Installation Guide

> **AURa** — Autonomous Universal Resource Architecture · v2.1.0

This guide covers installation on **Termux (Android/ARM64)**, Linux, and macOS.

---

## One-Command Installer (Termux)

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Cbetts1/Damn-it-xm/main/install.sh)
```

Or, if you have already cloned the repo:

```sh
bash install.sh
```

---

## Manual Installation

### 1 · Termux (Android, ARM64, No Root)

AURa is designed to run natively inside Termux without root, sudo, Docker, or virtualisation.

#### Prerequisites

```sh
pkg update -y
pkg install -y python git
pip install --upgrade pip
```

#### Clone & Install

```sh
cd $HOME
git clone https://github.com/Cbetts1/Damn-it-xm aura
cd aura
pip install -e .
```

#### Verify

```sh
aura version
aura status
```

---

### 2 · Linux / macOS

```sh
git clone https://github.com/Cbetts1/Damn-it-xm aura
cd aura
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
aura version
```

---

## Optional: Ollama (Large Language Model Backend)

AURa includes a built-in AI engine that works with zero dependencies. If you
want to run a full large language model (e.g. llama3.1:8b), install Ollama:

### Termux (ARM64)

```sh
pkg install -y ollama
ollama pull llama3.1:8b      # ~4.4 GB download
```

Set the environment variable before starting AURa:

```sh
export AURA_AI_BACKEND=openai_compatible
export AURA_API_BASE_URL=http://localhost:11434
export AURA_OLLAMA_MODEL=llama3.1:8b
aura shell
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AURA_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `AURA_DATA_DIR` | `~/.aura` | Data directory |
| `AURA_AI_BACKEND` | `builtin` | AI backend (`builtin`, `openai_compatible`) |
| `AURA_MODEL_NAME` | `aura-assistant` | AI model name |
| `AURA_SERVER_PORT` | `8000` | Virtual server HTTP port |
| `AURA_API_TOKEN` | _(none)_ | Bearer token for API authentication |
| `AURA_ROOT_SECRET` | _(default)_ | ROOT layer signing secret — change in production |
| `AURA_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `AURA_OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name |
| `AURA_NODE_NAME` | `aura-node` | Virtual node name for the mesh |
| `AURA_COMMAND_CENTER_URL` | _(none)_ | Command Center URL for node registration |
| `AURA_HEARTBEAT_INTERVAL` | `30.0` | Heartbeat interval in seconds |
| `AURA_REMOTE_ENABLED` | `false` | Enable the TCP remote control server |
| `AURA_REMOTE_PORT` | `8765` | Remote control server port (Termux-safe) |
| `AURA_REMOTE_TOKEN` | _(none)_ | Bearer token for remote control authentication |
| `AURA_BUILDER_DIR` | `~/.aura/builder` | Builder engine output directory |
| `AURA_BOOT_DEVICE` | _(none)_ | SD-card / external-storage boot path |

---

## Updating

```sh
cd ~/aura
git pull
pip install -e .
aura version
```

Or use the built-in upgrade script:

```sh
bash upgrade.sh
```

---

## Uninstalling

```sh
pip uninstall aura-ai-os -y
rm -rf ~/aura ~/.aura
```

---

## Paths (Termux)

| Path | Purpose |
|---|---|
| `/data/data/com.termux/files/home/aura/` | AURa repo root |
| `/data/data/com.termux/files/home/.aura/` | AURa data directory |
| `/data/data/com.termux/files/home/.aura/node_id` | Persistent virtual node UUID |
| `/data/data/com.termux/files/home/.aura/builder/` | Auto-generated modules |
| `/data/data/com.termux/files/home/.aura/model_cache/` | AI model cache |
| `/data/data/com.termux/files/home/.aura/packages/` | Installed packages |
| `/data/data/com.termux/files/home/.aura/audit.jsonl` | Audit log |
| `/data/data/com.termux/files/home/.aura/state.json` | Persisted state |

---

## Troubleshooting

**`command not found: aura`**
```sh
# Make sure pip's bin directory is on your PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

**Python 3.9+ required**
```sh
pkg install python    # Termux always ships a recent Python
python --version
```

**Port conflicts**
```sh
# Change the virtual server port
export AURA_SERVER_PORT=8080
```

**Ollama not reachable**
AURa falls back to the built-in AI engine gracefully if Ollama is not running.
No action needed — check `aura cloud-ai status` for details.
