# Contributing to AURa

Thank you for your interest in contributing to AURa — Autonomous Universal Resource Architecture.
This document describes how to get your changes merged quickly and correctly.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Branching Model](#branching-model)
5. [Coding Standards](#coding-standards)
6. [Tests](#tests)
7. [Submitting a Pull Request](#submitting-a-pull-request)
8. [Reporting Bugs](#reporting-bugs)
9. [Feature Requests](#feature-requests)

---

## Code of Conduct

All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Violations should be reported to the maintainers.

---

## Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/Cbetts1/Damn-it-xm.git
cd Damn-it-xm

# 2. Create a virtual environment (Python 3.9+)
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install AURa in editable mode (no external deps required)
pip install -e .

# 4. Run the test suite
python -m pytest tests/test_aura.py -v

# 5. Start AURa
python main.py shell
```

AURa has **zero required external dependencies**. All features in the core package
use only the Python standard library.

---

## Project Structure

```
aura/
  adapters/          — Platform bridge adapters (Android, Termux, Linux)
  ai_engine/         — Pluggable AI inference backend
  cloud/             — Virtual distributed cloud layer
  command_center/    — TUI live monitor
  cpu/               — Virtual task scheduler (virtual CPU)
  os_core/           — Central AI OS orchestrator (AIOS)
  persistence/       — SQLite-backed key-value + file store
  plugins/           — Plugin ABC and PluginManager
  server/            — HTTP API server + web dashboard
  shell/             — Interactive REPL + command executor + menu
  utils/             — Shared helpers (logger, IDs, EventBus)
  config.py          — Centralised configuration dataclasses
  main.py            — CLI entry point dispatcher
tests/
  test_aura.py       — Full test suite (46+ tests)
```

---

## Branching Model

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases only |
| `develop` | Integration branch for features |
| `feature/<name>` | Individual feature branches |
| `fix/<name>` | Bug-fix branches |
| `docs/<name>` | Documentation-only branches |

All PRs must target `develop` (not `main`).

---

## Coding Standards

- **Python 3.9+** syntax only.
- **stdlib-only** in `aura/` core. Optional deps (transformers, httpx) are opt-in via extras.
- Follow **PEP 8**. Use 4-space indentation. Max line length 120 characters.
- Every public class and function must have a **docstring**.
- Use **type hints** on all public function signatures.
- Use `aura.utils.get_logger("aura.<module>")` for all logging — never `print()` in library code.
- No `TODO` or `FIXME` in merged code — open an issue instead.
- No credentials, tokens, or secrets in source code.

---

## Tests

- All new code must have corresponding tests in `tests/test_aura.py`.
- Tests must pass in a clean environment with zero external dependencies.
- Do not modify or delete existing tests.
- Use `tmp_path` or `/tmp` for any file system operations in tests.

```bash
# Run the full suite
python -m pytest tests/test_aura.py -v

# Run a specific test
python -m pytest tests/test_aura.py::test_persistence_set_get -v
```

---

## Submitting a Pull Request

1. Fork the repository and create your branch from `develop`.
2. Write your code and tests.
3. Run `python -m pytest tests/test_aura.py -v` — all tests must pass.
4. Push your branch and open a PR against `develop`.
5. Fill in the PR template completely.
6. A maintainer will review within 5 business days.

**PR checklist:**
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Docstrings on all public APIs
- [ ] No external dependencies added without discussion
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

---

## Reporting Bugs

Open a GitHub Issue and include:
- AURa version (`aura version` in the shell)
- Python version and OS
- Exact error message and traceback
- Minimal reproduction steps

---

## Feature Requests

Open a GitHub Issue with the label `enhancement`. Describe:
- The problem you are solving
- Your proposed solution
- Any alternative approaches you considered

---

*Thank you for making AURa better.*
