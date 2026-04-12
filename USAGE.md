# AURa Usage Guide

> **AURa** — Autonomous Universal Resource Architecture · v2.1.0

---

## Quick Start

```sh
aura shell          # interactive shell
aura status         # one-shot status check
aura metrics        # JSON metrics dump
aura ask "hello"    # single AI query
aura help           # full command reference
```

---

## Interactive Shell

```sh
aura shell
```

The shell starts, prints the boot banner, and drops you into the AURa prompt:

```
AURa> _
```

Type any command from the list below.  Unknown input is forwarded to the AI engine.

### Tab Completion & History

- **Tab** — auto-completes commands and sub-commands
- **Up/Down** — navigate history (readline)
- **Ctrl-C** — cancel current input
- **exit** / **quit** — exit the shell

---

## Core Commands

| Command | Description |
|---|---|
| `status` | System health overview (all components) |
| `metrics` | Detailed JSON metrics for all subsystems |
| `version` | Show AURa version |
| `platform` | Show detected platform capabilities |
| `banner` | Show the AURa boot banner |
| `help` / `?` | Show full command reference |
| `exit` / `quit` | Exit the shell |

---

## AI Engine

| Command | Description |
|---|---|
| `ask <query>` | Query the built-in AI engine |
| `plan <task>` | Generate a task execution plan |
| `analyse` | AI analysis of current system metrics |
| `history` | Show conversation history |
| `clear_history` | Clear conversation history |

---

## Cloud AI Router (Ollama / LLM)

Requires Ollama to be running (`ollama serve`).

| Command | Description |
|---|---|
| `cloud-ai status` | Show Cloud AI Router status |
| `cloud-ai ask <question>` | Ask the large language model |
| `cloud-ai models` | List models cached in the virtual cloud |
| `cloud-ai list` | List models available on the Ollama server |
| `cloud-ai pull [model]` | Download a model to the virtual cloud |

---

## Virtual Infrastructure

| Command | Description |
|---|---|
| `cloud` | Virtual cloud metrics (nodes, storage, tasks) |
| `cpu` | Virtual CPU metrics (cores, queue, tasks) |
| `server` | Virtual server info (port, requests, routes) |
| `nodes` | List virtual cloud compute nodes |
| `models` | List registered AI models |
| `tasks` | List virtual CPU tasks |

---

## Virtual Hardware Devices

| Command | Description |
|---|---|
| `dev` | List all `/dev/*` virtual hardware devices |
| `vram` | Virtual RAM device status |
| `vdisk` | Virtual disk device status |
| `vgpu` | Virtual GPU / compute dispatcher status |

---

## Virtual Network Node (v2.1.0)

Each AURa installation acts as a **node** in a virtual mesh of repos.

| Command | Description |
|---|---|
| `vnode status` | Show this node's identity, registration status, heartbeat |
| `vnode id` | Print the stable node UUID |
| `vnode peers` | List peers registered in the local mesh bus |
| `vnode register` | Manually trigger registration with the Command Center |

### Node Configuration

```sh
export AURA_NODE_NAME="my-phone"
export AURA_COMMAND_CENTER_URL="http://command-center.example.com"
export AURA_HEARTBEAT_INTERVAL=30
aura shell
```

---

## Remote Control Server (v2.1.0)

A Termux-safe TCP/HTTP server (port 8765, no root required) that exposes the
AURa WebAPI for remote orchestration.

### Enable and Start

```sh
export AURA_REMOTE_ENABLED=true
export AURA_REMOTE_PORT=8765
export AURA_REMOTE_TOKEN=my-secret-token   # optional
aura shell
```

Or from the shell at runtime:

```
AURa> remote start
```

### Interact via HTTP

```sh
# Health check
curl http://phone-ip:8765/health

# System status
curl http://phone-ip:8765/status

# Run a command
curl -X POST http://phone-ip:8765/command \
  -H "Content-Type: application/json" \
  -d '{"command": "status"}'

# With auth token
curl -H "Authorization: Bearer my-secret-token" \
  http://phone-ip:8765/health
```

| Shell Command | Description |
|---|---|
| `remote status` | Show remote server status |
| `remote start` | Start the remote control server |
| `remote stop` | Stop the remote control server |

---

## Builder Engine (v2.1.0)

The builder engine **generates new modules, scripts, and configs** so AURa can
self-expand without manual coding.

| Command | Description |
|---|---|
| `builder status` | Show engine status and counts |
| `builder module <name> [desc]` | Generate a Python module skeleton |
| `builder script <name> [desc]` | Generate a POSIX shell script |
| `builder config <name>` | Generate a JSON config file |
| `builder list` | List all generated artefacts |

### Example

```
AURa> builder module data_scraper "Scrapes external data sources"
Module generated: /home/user/.aura/builder/data_scraper.py

AURa> builder script deploy "Deploys to production"
Script generated: /home/user/.aura/builder/deploy.sh

AURa> builder list
Builder artefacts (2):
  [module  ] data_scraper   /home/user/.aura/builder/data_scraper.py
  [script  ] deploy         /home/user/.aura/builder/deploy.sh
```

---

## Kernel Services

| Command | Description |
|---|---|
| `kernel` | Kernel services summary |
| `proc [list/kill <pid>]` | Process manager |
| `syslog [last <n>]` | System log viewer |
| `cron list/add/remove` | Cron job management |
| `svc list/start/stop` | Service manager |

---

## Filesystem

| Command | Description |
|---|---|
| `fs ls [path]` | List directory |
| `fs mkdir <path>` | Create directory |
| `fs write <path> <content>` | Write file |
| `fs read <path>` | Read file |
| `fs rm <path>` | Remove file/directory |
| `fs info <path>` | File info |
| `vfs …` | Virtual filesystem operations |

---

## Package Manager

| Command | Description |
|---|---|
| `pkg list` | List installed packages |
| `pkg install <name>` | Install a package |
| `pkg remove <name>` | Remove a package |
| `pkg git <url>` | Install from git repo |
| `apkg …` | AURa package registry operations |

---

## Build Pipeline

| Command | Description |
|---|---|
| `build run <name> [version]` | Run a build pipeline |
| `build list` | List all build runs |
| `build approve <id>` | Approve a pending build |
| `build reject <id>` | Reject a pending build |

---

## Identity & Security

| Command | Description |
|---|---|
| `identity` | Identity registry status |
| `audit [last <n>]` | Audit log entries |
| `root` | ROOT sovereign layer status |

---

## Network Stack

| Command | Description |
|---|---|
| `net` | Full network stack status |
| `net dns <name>` | Resolve a name via virtual DNS |

---

## HOME Userland

| Command | Description |
|---|---|
| `home` | HOME userland status |

---

## Mirror & Intelligence

| Command | Description |
|---|---|
| `mirror` | Mirror service status |
| `intel` | Intelligence index summary |
| `personality` | AI personality kernel status |
| `modelreg` | AI model registry |

---

## Shell Utilities

| Command | Description |
|---|---|
| `bash <cmd>` | Run a host shell command |
| `!<cmd>` | Shorthand for `bash <cmd>` |
| `kv set <k> <v>` | Store a key-value pair |
| `kv get <k>` | Retrieve a stored value |
| `kv list` | List all stored keys |
| `kv del <k>` | Delete a stored key |
| `git clone/pull/status` | Git operations |
| `plugins` | List registered plugins |

---

## Python API

You can also drive AURa programmatically:

```python
from aura.os_core.ai_os import AIOS
from aura.config import AURaConfig

cfg = AURaConfig.from_env()
with AIOS(cfg) as aios:
    print(aios.status())
    print(aios.dispatch("ask", ["what is your purpose?"]))
    print(aios.vnode_identity.to_dict())
    aios.builder_engine.generate_module("my_plugin", "Auto-generated plugin")
```

---

## One-Command Examples

```sh
# Start the interactive shell
aura shell

# Print system status and exit
aura status

# Ask the AI a question
aura ask "Explain the AURa architecture"

# Start with remote control enabled
AURA_REMOTE_ENABLED=true AURA_REMOTE_PORT=8765 aura shell

# Start with a custom node name and Command Center
AURA_NODE_NAME=termux-phone \
AURA_COMMAND_CENTER_URL=http://my-server.example.com \
aura shell
```

---

## Command Center Integration

AURa nodes self-register with the Command Center and send periodic heartbeats.
The Command Center can then:

- Query node status via `GET /api/nodes`
- Push commands via `POST /api/nodes/{node_id}/command`
- Receive structured JSON metrics
- Trigger builds or module generation remotely

See [INSTALL.md](INSTALL.md) for environment variable configuration.
