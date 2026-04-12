#!/bin/sh
# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
#
# AURa — One-Command Installer for Termux (Android ARM64)
# =========================================================
#
# Usage:
#   bash <(curl -fsSL https://raw.githubusercontent.com/Cbetts1/Damn-it-xm/main/install.sh)
#
# Or, if you have already cloned the repo:
#   bash install.sh
#
# This script:
#   1. Detects whether it is running inside Termux or on a regular Linux/macOS host
#   2. Installs required system packages (Termux only)
#   3. Clones (or updates) the AURa repository
#   4. Installs Python dependencies
#   5. Creates the data directory at ~/.aura
#   6. Writes a .env template if none exists
#   7. Optionally installs Ollama (Termux only)
#   8. Verifies the installation with `aura version`
#
# Requirements:
#   - Termux (Android) OR Linux/macOS with Python 3.9+
#   - No root, no sudo, no Docker
#
# Environment overrides (set before running):
#   AURA_DIR          Install directory  (default: $HOME/aura)
#   AURA_REPO         Git repository URL (default: GitHub)
#   AURA_BRANCH       Git branch         (default: main)
#   AURA_SKIP_OLLAMA  Set to "1" to skip Ollama install prompt

set -eu

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AURA_REPO="${AURA_REPO:-https://github.com/Cbetts1/Damn-it-xm}"
AURA_BRANCH="${AURA_BRANCH:-main}"
AURA_DIR="${AURA_DIR:-$HOME/aura}"
AURA_DATA_DIR="$HOME/.aura"
AURA_ENV_FILE="$AURA_DATA_DIR/.env"
AURA_SKIP_OLLAMA="${AURA_SKIP_OLLAMA:-0}"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
_bold=""
_green=""
_yellow=""
_red=""
_reset=""
if [ -t 1 ]; then
    _bold="\033[1m"
    _green="\033[32m"
    _yellow="\033[33m"
    _red="\033[31m"
    _reset="\033[0m"
fi

info()    { printf "${_green}[AURa]${_reset} %s\n" "$*"; }
warn()    { printf "${_yellow}[WARN]${_reset} %s\n" "$*"; }
error()   { printf "${_red}[ERROR]${_reset} %s\n" "$*" >&2; exit 1; }
header()  { printf "\n${_bold}%s${_reset}\n" "────────────────────────────────────────"; }

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
IS_TERMUX=0
if [ -d "/data/data/com.termux" ]; then
    IS_TERMUX=1
fi

header
info "AURa Installer  (repo: $AURA_REPO)"
info "Platform       : $([ "$IS_TERMUX" = "1" ] && echo "Termux/Android" || echo "Linux/macOS")"
info "Install dir    : $AURA_DIR"
info "Data dir       : $AURA_DATA_DIR"

# ---------------------------------------------------------------------------
# 1. System packages (Termux only)
# ---------------------------------------------------------------------------
header
info "Step 1/8 — Installing system packages…"
if [ "$IS_TERMUX" = "1" ]; then
    pkg update -y
    pkg install -y python git
    info "  python and git installed."
else
    # On Linux/macOS we rely on the user having Python 3 and git already
    command -v python3 >/dev/null 2>&1 || error "python3 not found — please install Python 3.9+"
    command -v git     >/dev/null 2>&1 || error "git not found — please install git"
    info "  python3 and git already available."
fi

# ---------------------------------------------------------------------------
# 2. Ensure pip is up-to-date
# ---------------------------------------------------------------------------
header
info "Step 2/8 — Upgrading pip…"
python3 -m ensurepip --upgrade 2>/dev/null || true
python3 -m pip install --upgrade pip --quiet
info "  pip ready."

# ---------------------------------------------------------------------------
# 3. Clone or update the repo
# ---------------------------------------------------------------------------
header
info "Step 3/8 — Cloning/updating AURa repository…"
if [ -d "$AURA_DIR/.git" ]; then
    info "  Existing repo found at $AURA_DIR — pulling latest changes."
    git -C "$AURA_DIR" fetch --quiet origin
    git -C "$AURA_DIR" checkout "$AURA_BRANCH" --quiet
    git -C "$AURA_DIR" pull --quiet --ff-only origin "$AURA_BRANCH"
else
    info "  Cloning $AURA_REPO into $AURA_DIR…"
    git clone --branch "$AURA_BRANCH" --depth 1 "$AURA_REPO" "$AURA_DIR"
fi
info "  Repository ready."

# ---------------------------------------------------------------------------
# 4. Install Python package (editable)
# ---------------------------------------------------------------------------
header
info "Step 4/8 — Installing AURa Python package…"
python3 -m pip install --quiet -e "$AURA_DIR"
info "  Package installed."

# ---------------------------------------------------------------------------
# 5. Create data directory
# ---------------------------------------------------------------------------
header
info "Step 5/8 — Creating data directory…"
mkdir -p "$AURA_DATA_DIR"
mkdir -p "$AURA_DATA_DIR/model_cache"
mkdir -p "$AURA_DATA_DIR/packages"
mkdir -p "$AURA_DATA_DIR/artefacts"
mkdir -p "$AURA_DATA_DIR/builder"
info "  Data directory created: $AURA_DATA_DIR"

# ---------------------------------------------------------------------------
# 6. Write .env template (if none exists)
# ---------------------------------------------------------------------------
header
info "Step 6/8 — Writing environment template…"
if [ -f "$AURA_ENV_FILE" ]; then
    info "  $AURA_ENV_FILE already exists — skipping."
else
    cat > "$AURA_ENV_FILE" << 'ENV_EOF'
# AURa Environment Configuration
# Source this file before running AURa:  source ~/.aura/.env

# Core settings
export AURA_LOG_LEVEL=INFO
export AURA_DATA_DIR="$HOME/.aura"

# AI backend (builtin | openai_compatible)
export AURA_AI_BACKEND=builtin
export AURA_MODEL_NAME=aura-assistant

# Virtual server
export AURA_SERVER_PORT=8000

# Ollama (uncomment if installed)
# export AURA_OLLAMA_URL=http://localhost:11434
# export AURA_OLLAMA_MODEL=llama3.1:8b

# Virtual network node
export AURA_NODE_NAME=aura-node
# export AURA_COMMAND_CENTER_URL=http://command-center.example.com
# export AURA_HEARTBEAT_INTERVAL=30

# Remote control server (disabled by default)
# export AURA_REMOTE_ENABLED=true
# export AURA_REMOTE_PORT=8765
# export AURA_REMOTE_TOKEN=change-me
ENV_EOF
    info "  Template written to $AURA_ENV_FILE"
    info "  Edit it and run: source $AURA_ENV_FILE"
fi

# ---------------------------------------------------------------------------
# 7. Ensure `aura` is on PATH
# ---------------------------------------------------------------------------
header
info "Step 7/8 — Checking PATH…"

# Pip user-install bin dir
if [ "$IS_TERMUX" = "1" ]; then
    PIP_BIN="$HOME/.local/bin"
else
    PIP_BIN="$(python3 -m site --user-base 2>/dev/null)/bin"
fi

case ":$PATH:" in
    *":$PIP_BIN:"*) info "  $PIP_BIN already in PATH." ;;
    *)
        info "  Adding $PIP_BIN to PATH…"
        SHELL_RC="$HOME/.bashrc"
        [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
        if ! grep -q "AURA_PATH_ADDED" "$SHELL_RC" 2>/dev/null; then
            {
                echo ""
                echo "# AURa — added by install.sh  # AURA_PATH_ADDED"
                echo "export PATH=\"$PIP_BIN:\$PATH\""
            } >> "$SHELL_RC"
            info "  PATH updated in $SHELL_RC — restart your shell or run: export PATH=\"$PIP_BIN:\$PATH\""
        fi
        export PATH="$PIP_BIN:$PATH"
        ;;
esac

# ---------------------------------------------------------------------------
# 8. Verify installation
# ---------------------------------------------------------------------------
header
info "Step 8/8 — Verifying installation…"
if command -v aura >/dev/null 2>&1; then
    AURA_VER=$(aura version 2>/dev/null | head -1 || true)
    info "  OK — AURa found: $AURA_VER"
else
    # Try via python directly in case PATH not refreshed yet
    AURA_VER=$(python3 -m aura version 2>/dev/null | head -1 || true)
    if [ -n "$AURA_VER" ]; then
        info "  OK — AURa found (via python -m aura): $AURA_VER"
        warn "  Run: export PATH=\"$PIP_BIN:\$PATH\"  to use the 'aura' command directly."
    else
        warn "  'aura' command not found in PATH."
        warn "  Run: export PATH=\"$PIP_BIN:\$PATH\"  then try: aura version"
    fi
fi

# ---------------------------------------------------------------------------
# Optional: Ollama (Termux only)
# ---------------------------------------------------------------------------
if [ "$IS_TERMUX" = "1" ] && [ "$AURA_SKIP_OLLAMA" = "0" ]; then
    header
    printf "${_yellow}[?]${_reset} Install Ollama for large-model AI support? (y/N) "
    read -r _answer || _answer="n"
    case "$_answer" in
        [yY]*)
            info "Installing Ollama…"
            pkg install -y ollama || warn "Ollama install failed — you can install it later with: pkg install ollama"
            ;;
        *)
            info "Skipping Ollama (you can install it later with: pkg install ollama)"
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
header
info ""
info "  ✅  AURa installation complete!"
info ""
info "  Next steps:"
info "    1. Source your environment:    source $AURA_ENV_FILE"
info "    2. Start the shell:            aura shell"
info "    3. Check status:               aura status"
info "    4. Read the docs:              cat $AURA_DIR/USAGE.md"
info ""
