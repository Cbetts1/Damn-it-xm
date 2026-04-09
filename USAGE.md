# AURa Usage Guide

This guide covers every command and mode available in AURa v1.1.

---

## Starting AURa

```bash
aura shell       # Interactive shell (default)
aura server      # Start API server only
aura monitor     # Start TUI live monitor
aura status      # Print status and exit
aura ask <q>     # Ask AI a question and exit
python main.py   # Same as: aura shell
```

---

## AURa Shell Commands

Once inside the shell, type `help` to see all commands.

### System Commands

| Command | Description |
|---------|-------------|
| `status` | System health overview (all components) |
| `metrics` | Detailed component metrics |
| `version` | Show AURa version |
| `help` | Show command list |
| `exit` / `quit` | Exit AURa |
| `clear` | Clear the terminal screen |

### Virtual Infrastructure

| Command | Description |
|---------|-------------|
| `cloud` | Virtual cloud metrics |
| `cpu` | Virtual CPU metrics |
| `server` | Virtual server info and URLs |
| `nodes` | List cloud compute nodes |
| `models` | List registered AI models |
| `tasks` | Show CPU task queue history |

### AI Engine

| Command | Description |
|---------|-------------|
| `ask <question>` | Query the AI engine |
| `plan <task>` | Generate AI task execution plan |
| `analyse` | AI analysis of current system metrics |
| `history` | Show conversation history |
| `clear_history` | Clear conversation history |

### Shell & Bash Execution

| Command | Description |
|---------|-------------|
| `bash <cmd>` | Run any Linux/Termux/bash command |
| `!<cmd>` | Shorthand for `bash <cmd>` |
| `pwd` | Print working directory |
| `cd <path>` | Change directory |
| `ls [-la] [path]` | List directory |
| `mkdir [-p] <dir>` | Create directory |
| `rm [-rf] <path>` | Remove file or directory |
| `cp <src> <dst>` | Copy file |
| `mv <src> <dst>` | Move / rename |
| `cat <file>` | Print file contents |
| `echo <text>` | Print text |
| `env` | Show environment variables |
| `export KEY=VALUE` | Set environment variable |
| `which <cmd>` | Find command location |
| `uname [-a]` | System info |
| `whoami` | Current user |
| `date` | Current date and time |
| `uptime` | System uptime |
| `df [-h]` | Disk usage |
| `free [-h]` | Memory usage |
| `ps [aux]` | Process list |

**Any command not in the list above is forwarded to the system shell (subprocess).**

Examples:
```
AURa> !git status
AURa> bash pip list
AURa> bash python3 --version
AURa> bash ls -la /tmp
```

### Persistence Storage

| Command | Description |
|---------|-------------|
| `store <ns> <key> <value>` | Persist a value in namespace `ns` |
| `retrieve <ns> <key>` | Retrieve a stored value |
| `listkeys <ns>` | List all keys in namespace |

Examples:
```
AURa> store config theme dark
AURa> retrieve config theme
dark
AURa> listkeys config
theme
```

### Plugins

| Command | Description |
|---------|-------------|
| `plugins` | List loaded plugins and their commands |
| `sysinfo` | Detailed system information (SystemInfoPlugin) |
| `store <ns> <key> <value>` | Store via StoragePlugin |
| `retrieve <ns> <key>` | Retrieve via StoragePlugin |

### Platform & Android

| Command | Description |
|---------|-------------|
| `platform` | Show platform capabilities and environment |

Example output:
```
Platform: Linux x86_64
Bash: /bin/bash
Python: /usr/bin/python3
Git: /usr/bin/git
Android: No
Termux: No
```

### Menu Workspace

```
AURa> menu
```

Opens the numbered menu interface:
```
╔══════════════════════════════════╗
║     AURa Workspace Menu          ║
╠══════════════════════════════════╣
║  1. Shell                        ║
║  2. AI Chat                      ║
║  3. System Status                ║
║  4. Cloud Manager                ║
║  5. CPU Monitor                  ║
║  6. Server Dashboard             ║
║  7. Storage Manager              ║
║  8. Android Bridge               ║
║  9. Plugin Manager               ║
║  0. Exit AURa                    ║
╚══════════════════════════════════╝
```

---

## Web Dashboard

Once AURa is running, open your browser:

- **Dashboard**: http://localhost:8000/dashboard
- **API**: http://localhost:8000/api/v1/status
- **Health**: http://localhost:8000/health

---

## REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/status` | Full system status |
| GET | `/api/v1/metrics` | Component metrics |
| POST | `/api/v1/ask` | Query AI engine |
| POST | `/api/v1/task` | Submit CPU task |
| GET | `/api/v1/cloud` | Cloud status |
| GET | `/api/v1/cpu` | CPU metrics |
| GET | `/api/v1/models` | Registered AI models |
| GET | `/dashboard` | Web command center |

**POST /api/v1/ask example:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AURa?"}'
```

---

## Data Directory

AURa stores all persistent data in `~/.aura/` (configurable via `AURA_DATA_DIR`):

```
~/.aura/
  aura.db            — SQLite persistence database
  model_cache/       — Cached AI model files
  .shell_history     — AURa shell command history
  cloud_storage/     — Virtual cloud file storage
```
