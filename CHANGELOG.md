# Changelog

All notable changes to AURa are documented in this file.
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] — 2026-04-09

### Added
- **Legal & Compliance suite**: `LICENSE` (MIT), `TERMS_OF_USE.md`,
  `PRIVACY_NOTICE.md`, `DISCLAIMER.md`, and `CHANGELOG.md` added to repo.
- **Copyright headers**: SPDX `MIT` copyright headers added to every Python
  source file.
- **Full validation report** in README: 98 tests, 17 s, 100% pass rate.
- **Termux installation badge** and per-platform install instructions in
  README.
- **Architecture badge row** in README (version, license, Python, Termux).

### Changed
- Version bumped from **1.1.0 → 1.2.0** across all files:
  `__init__.py`, `config.py`, `setup.py`, `upgrade.sh`,
  `shell.py` banner, `engine.py` builtin knowledge dict,
  `ai_os.py` `VERSION` constant, `virtual_server.py` dashboard HTML.
- README rewritten: correct version strings (was `v1.0.0`), updated
  validation table, expanded Termux install section, legal section added.

### Fixed
- Stale `v1.0.0` version reference in the README validation smoke-test
  output block.

---

## [1.1.0] — 2026-04-08

### Added
- **Shell command executor** (`aura/shell/commands.py`): built-in
  implementations of `pwd`, `echo`, `cd`, `ls`, `mkdir`, `touch`, `cat`,
  `wc`, `date`, `uname`, `which`, `df`.
- `!`-shorthand in the AI OS dispatcher: `! <cmd>` runs a shell command.
- 10 new shell-executor tests.
- Android / Termux bridge (`aura/adapters/android_bridge.py`): detects
  platform capabilities, exposes `subprocess_run` for the shell executor.
- History persistence via `PersistenceEngine` (SQLite).

### Changed
- Version bumped from 1.0.0 → 1.1.0.
- AI OS `dispatch()` now routes `bash`, `exec`, and `!` prefixes to the
  shell executor.
- `upgrade.sh` updated to verify all new modules.

---

## [1.0.0] — 2026-03-15

### Added
- Initial release: AI OS, Virtual CPU, Virtual Cloud, Virtual Server,
  AI Engine (builtin / Transformers / OpenAI-compatible backends),
  Command Center TUI monitor, Plugin Manager, Persistence Engine, Shell
  REPL, and REST API server.
- Zero-dependency mode (builtin backend works completely offline).
- `upgrade.sh` one-command Termux/Linux installer.
- 32 integration tests.
