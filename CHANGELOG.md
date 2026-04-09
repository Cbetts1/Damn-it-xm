# Changelog

All notable changes to AURa are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Persistence engine (`aura/persistence/store.py`) — SQLite-backed namespaced key-value store with binary file management
- Android/Termux bridge adapter (`aura/adapters/android_bridge.py`) — platform capability detection and cross-platform command runner
- Full shell command emulator (`aura/shell/commands.py`) — 20 built-in POSIX commands plus subprocess fallback for any Linux/Termux command
- Menu-driven workspace (`aura/shell/commands.py:MenuWorkspace`) — numbered menu interface for all subsystems
- Plugin architecture (`aura/plugins/manager.py`) — `AURaPlugin` ABC, `PluginManager`, built-in `SystemInfoPlugin` and `StoragePlugin`
- Capability-aware boot sequence in AIOS — detects platform, initialises persistence and plugins at startup
- New shell commands: `bash <cmd>`, `!<cmd>`, `menu`, `store`, `retrieve`, `platform`, `plugins`
- Dynamic cwd-aware shell prompt
- `persistence_db` config field with `AURA_DB_PATH` env override
- 14 new tests (46 total, all passing)

### Documentation
- `LICENSE` (MIT)
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `CHANGELOG.md` (this file)
- `ROADMAP.md`
- `INSTALL.md`
- `USAGE.md`
- `TERMS.md`
- `PRIVACY.md`
- `DISCLAIMER.md`
- `COPYRIGHT.md`
- `AI_DISCLOSURE.md`

---

## [1.0.0] — 2026-04-08

### Added
- Initial AURa AI OS release
- Virtual Cloud (8 nodes, 1 TB virtual storage, model registry)
- Virtual CPU (64 vCores, 256-thread task queue)
- Virtual Server (HTTP API + web dashboard at `/dashboard`)
- AI Engine with builtin, transformers, and openai_compatible backends
- AURa interactive shell (REPL with readline, tab-completion, colour prompt)
- TUI live monitor (command center)
- 32 tests covering all core subsystems
- README.md with architecture diagram
