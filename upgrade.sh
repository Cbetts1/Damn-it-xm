#!/usr/bin/env bash
# =============================================================================
# AURa v1.2.0 — One-Command Upgrade Script
# Compatible with: Termux (Android), Linux, macOS, WSL
#
# Usage:
#   bash upgrade.sh          # upgrade in-place (current directory)
#   bash upgrade.sh --check  # dry-run: check only, no changes
#   bash upgrade.sh --force  # skip version check and re-apply
#
# What this script does:
#   1. Verifies Python 3.9+ is available
#   2. Pulls the latest changes from the remote repository (if git is present)
#   3. Installs / upgrades optional dependencies (pytest for validation)
#   4. Runs the full test suite to confirm 100% pass rate
#   5. Prints a post-upgrade system status summary
#
# No root access required. No external build tools required.
# Runs entirely within the AURa project directory.
# =============================================================================

set -euo pipefail

# --- Colours -----------------------------------------------------------------
BOLD="\033[1m"
CYAN="\033[96m"
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
DIM="\033[2m"
RESET="\033[0m"

AURA_VERSION="1.2.0"
DRY_RUN=false
FORCE=false

# --- Argument parsing --------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --check) DRY_RUN=true ;;
    --force) FORCE=true ;;
    --help|-h)
      echo "Usage: bash upgrade.sh [--check] [--force]"
      echo "  --check   Dry-run only — report what would change"
      echo "  --force   Skip version check and re-apply upgrade"
      exit 0
      ;;
  esac
done

# --- Banner ------------------------------------------------------------------
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║   AURa v${AURA_VERSION}  —  System Upgrade Script              ║"
echo "  ║   Autonomous Universal Resource Architecture         ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log()  { echo -e "${BOLD}[AURa]${RESET} $*"; }
ok()   { echo -e "${GREEN}  ✅ $*${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠️  $*${RESET}"; }
fail() { echo -e "${RED}  ❌ $*${RESET}"; exit 1; }

# --- Step 1: Python version check -------------------------------------------
log "Checking Python version…"
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
  fail "Python not found. Install Python 3.9+ via your package manager."
fi

PYTHON_BIN="python3"
command -v python3 &>/dev/null || PYTHON_BIN="python"

PY_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON_BIN" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON_BIN" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  fail "Python ${PY_VERSION} found but 3.9+ is required."
fi
ok "Python ${PY_VERSION} — OK"

# --- Step 2: Pull latest changes (if git is available) ----------------------
log "Checking for repository updates…"
if command -v git &>/dev/null && [ -d ".git" ]; then
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  if [ "$DRY_RUN" = true ]; then
    warn "Dry-run mode: skipping git pull (branch: ${CURRENT_BRANCH})"
  else
    if git remote get-url origin &>/dev/null; then
      git fetch origin --quiet
      LOCAL=$(git rev-parse HEAD)
      REMOTE=$(git rev-parse "@{u}" 2>/dev/null || echo "$LOCAL")
      if [ "$LOCAL" = "$REMOTE" ] && [ "$FORCE" = false ]; then
        ok "Repository is already up to date (branch: ${CURRENT_BRANCH})"
      else
        log "Pulling latest changes from origin/${CURRENT_BRANCH}…"
        git pull --rebase origin "$CURRENT_BRANCH" --quiet
        ok "Repository updated to $(git rev-parse --short HEAD)"
      fi
    else
      warn "No remote 'origin' configured — skipping git pull"
    fi
  fi
else
  warn "git not available or not a git repo — skipping pull"
fi

# --- Step 3: Install/upgrade test dependencies ------------------------------
log "Ensuring test dependencies are available…"
if [ "$DRY_RUN" = false ]; then
  PIP_OUT=$("$PYTHON_BIN" -m pip install --quiet --upgrade pytest pytest-cov 2>&1)
  PIP_EXIT=$?
  if [ "$PIP_EXIT" -eq 0 ]; then
    ok "pytest installed/updated"
  else
    warn "pip install failed — will attempt to run tests with existing pytest"
    echo "$PIP_OUT" | tail -5
  fi
else
  warn "Dry-run mode: skipping pip install"
fi

# --- Step 4: Validate the installation imports correctly --------------------
log "Validating AURa package imports…"
if "$PYTHON_BIN" -c "
import sys, os
sys.path.insert(0, '.')
from aura import __version__
from aura.config import AURaConfig
from aura.os_core.ai_os import AIOS
from aura.shell.shell import AURaShell, parse_flags
from aura.cpu.virtual_cpu import VirtualCPU
from aura.cloud.virtual_cloud import VirtualCloud
from aura.server.virtual_server import VirtualServer
from aura.ai_engine.engine import AIEngine
print(f'AURa {__version__} — all modules imported successfully')
" 2>/dev/null; then
  ok "All AURa modules import without error"
else
  fail "Module import failed — check for syntax errors or missing files"
fi

# --- Step 5: Run the test suite ---------------------------------------------
log "Running full test suite…"
if [ "$DRY_RUN" = false ]; then
  if "$PYTHON_BIN" -m pytest tests/test_aura.py -v --tb=short 2>&1; then
    ok "All tests passed — system validated ✅"
  else
    fail "Test suite failed — upgrade aborted. Review output above."
  fi
else
  warn "Dry-run mode: skipping test suite"
fi

# --- Step 6: Post-upgrade status report -------------------------------------
log "Running post-upgrade system status check…"
"$PYTHON_BIN" main.py status 2>/dev/null || true

# --- Done --------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║   AURa v${AURA_VERSION} upgrade complete ✅                     ║"
echo "  ║   Run: python main.py shell                          ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
