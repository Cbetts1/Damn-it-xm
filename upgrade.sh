#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  AURa v1.1.0 — One-Command Upgrade Script (Termux & Linux)
# ──────────────────────────────────────────────────────────────
# Usage:
#   bash upgrade.sh          (from the repo root)
#
# What this does:
#   1. Verifies Python ≥ 3.8 is available.
#   2. Installs / upgrades pytest (the only dev dependency).
#   3. Runs the full test suite to validate the upgrade.
#   4. Reports success or failure.
#
# Safe:
#   • No root required.
#   • No heavy libraries.
#   • No network calls (unless pip needs to download pytest).
#   • Idempotent — can be run repeatedly.
# ──────────────────────────────────────────────────────────────

set -euo pipefail

CYAN='\033[96m'
GREEN='\033[92m'
RED='\033[91m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${CYAN}[INFO]${RESET}  %s\n" "$*"; }
ok()    { printf "${GREEN}[  OK]${RESET}  %s\n" "$*"; }
fail()  { printf "${RED}[FAIL]${RESET}  %s\n" "$*"; }

# ── 0. Check Python ─────────────────────────────────────────
info "Checking Python version…"
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3 not found.  Install with:  pkg install python  (Termux)"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
    fail "Python ≥ 3.8 required (found $PY_VERSION)"
    exit 1
fi
ok "Python $PY_VERSION"

# ── 1. Install pytest (dev dependency) ──────────────────────
info "Ensuring pytest is installed…"
"$PYTHON" -m pip install --quiet --upgrade pytest 2>/dev/null \
    || "$PYTHON" -m pip install --quiet --upgrade --user pytest 2>/dev/null \
    || { fail "Could not install pytest. Run: pip install pytest"; exit 1; }
ok "pytest ready"

# ── 2. Verify package structure ──────────────────────────────
info "Verifying AURa package structure…"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

for mod in aura/__init__.py aura/os_core/ai_os.py aura/cpu/virtual_cpu.py \
           aura/cloud/virtual_cloud.py aura/server/virtual_server.py \
           aura/ai_engine/engine.py aura/shell/shell.py aura/shell/commands.py \
           aura/persistence/store.py aura/plugins/manager.py \
           aura/adapters/android_bridge.py aura/command_center/monitor.py \
           aura/config.py main.py tests/test_aura.py; do
    if [ ! -f "$mod" ]; then
        fail "Missing module: $mod"
        exit 1
    fi
done
ok "All modules present"

# ── 3. Run full test suite ───────────────────────────────────
info "Running full test suite…"
if "$PYTHON" -m pytest tests/test_aura.py -v --tb=short; then
    echo ""
    ok "All tests passed ✓"
else
    echo ""
    fail "Some tests failed — please check output above."
    exit 1
fi

# ── 4. Version confirmation ──────────────────────────────────
VERSION=$("$PYTHON" -c "from aura import __version__; print(__version__)")
echo ""
printf "${BOLD}${GREEN}╔═══════════════════════════════════════════╗${RESET}\n"
printf "${BOLD}${GREEN}║  AURa v%-6s  UPGRADE COMPLETE  ✓       ║${RESET}\n" "$VERSION"
printf "${BOLD}${GREEN}╚═══════════════════════════════════════════╝${RESET}\n"
echo ""
info "To start AURa:  $PYTHON main.py shell"
info "To start the server:  $PYTHON main.py server"
info "To run the monitor:   $PYTHON main.py monitor"
