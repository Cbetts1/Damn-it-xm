# AURa Roadmap

This document describes the planned evolution of AURa — Autonomous Universal Resource Architecture — toward a full validation-ready AI-native OS.

---

## Vision

AURa is a universal, portable, AI-native virtual operating system. Its canonical rootfs can live on an SD card. Host-bridge adapters allow it to run in mirror mode (simulate the full OS) or hardware mode (directly control attached hardware). The AI engine is the only required physical component — all compute, storage, and networking are managed as virtual resources.

---

## Release Plan

### v1.1 — Shell & Infrastructure (Current Sprint)
- [x] Full bash/Linux command emulation in the AURa shell (20+ built-in commands + subprocess fallback)
- [x] Android/Termux capability detection and host-bridge adapter
- [x] SQLite persistence engine (namespaced KV store + binary file storage)
- [x] Plugin architecture with built-in SystemInfo and Storage plugins
- [x] Menu-driven workspace interface
- [x] Capability-aware boot sequence

### v1.2 — Networking & Gateway
- [ ] Virtual network stack (virtual NICs, routing table, DHCP simulation)
- [ ] Public gateway machine simulation (mini-ISP mode)
- [ ] Port-forwarding and NAT rule management via AURa shell
- [ ] DNS resolver integration (real system DNS + virtual overlay)
- [ ] Wireguard/SSH tunnel management helpers

### v1.3 — SD Card Rootfs & Boot
- [ ] Canonical rootfs manifest generator (directory tree + permissions)
- [ ] SD card image layout (boot partition, rootfs partition, data partition)
- [ ] Capability-aware boot script (detect hardware, load appropriate drivers/plugins)
- [ ] Mirror mode: full rootfs snapshot and restore
- [ ] Hardware mode: direct GPIO/USB/serial bridge on supported devices

### v1.4 — Advanced Plugin System
- [ ] Plugin registry (discover, install, remove plugins from plugin catalogue)
- [ ] Plugin sandboxing (restrict filesystem and network access per plugin)
- [ ] Hot-reload plugins without restarting AURa
- [ ] Plugin manifest format (name, version, deps, permissions)
- [ ] Community plugin catalogue

### v1.5 — AI Engine Upgrades
- [ ] Streaming responses (token-by-token output in the shell)
- [ ] Long-context conversation with summarisation
- [ ] Multi-model routing (route queries to the best available backend)
- [ ] Offline model management (download, cache, delete HuggingFace models)
- [ ] GGUF/llama.cpp backend support

### v2.0 — Dual-System Validation & Production
- [ ] AURA-AIOSCPU dual-system architecture (OS brain + hardware CPU bridge)
- [ ] Full OS identity governance (system ID, cryptographic signing)
- [ ] Threat model enforcement (capability-based access control)
- [ ] Formal API surface documentation (OpenAPI 3.1 spec)
- [ ] Rootfs integrity verification (hash manifest)
- [ ] Production TLS server with certificate management
- [ ] Multi-user session isolation
- [ ] Automated CI/CD pipeline for SD card image builds

---

## Long-Term Vision (v3+)

- Real-hardware integration with Raspberry Pi / Orange Pi SD-card deployments
- AURa mobile companion app (Android)
- Distributed mesh mode (multiple AURa nodes forming a local mesh network)
- Federated AI model sharing between AURa instances
- AIOS process model with real syscall emulation
