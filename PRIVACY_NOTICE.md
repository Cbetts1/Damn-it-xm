# AURa — Privacy Notice

**Effective Date:** 2026-04-09
**Project:** AURa — Autonomous Universal Resource Architecture
**Repository:** https://github.com/Cbetts1/Damn-it-xm

---

## 1. Overview

AURa is a local-first, offline-capable AI virtual operating system.
This notice explains what data AURa collects, stores, and transmits.

## 2. Data Collected Locally

When you run AURa, the following information may be stored **locally on your
device** in `~/.aura/`:

| Data | Purpose | Location |
|---|---|---|
| Conversation history | AI context window persistence | `~/.aura/aura.db` (SQLite) |
| KV store entries | User-defined key-value pairs | `~/.aura/aura.db` |
| Model cache files | Cached AI model weights (optional) | `~/.aura/model_cache/` |
| Log output | Debugging and diagnostics | stderr / `~/.aura/logs/` |

All data is stored exclusively on your local device.  AURa does **not**
transmit this data to any remote server unless you explicitly configure an
external AI backend (see Section 4).

## 3. No Telemetry

AURa does **not** collect telemetry, analytics, usage statistics, or crash
reports.  No data about your usage is sent anywhere by default.

## 4. Optional External AI Backends

If you configure the `openai_compatible` or `transformers` backend, AURa
will send your prompts (queries) to the endpoint you specify.  This is
entirely opt-in and under your control.  AURa is not responsible for the
privacy practices of third-party AI services you choose to connect.

## 5. No Personal Information Required

AURa does not require registration, login, email address, or any personally
identifiable information (PII) to operate.

## 6. Data Deletion

To delete all locally stored AURa data, remove the `~/.aura/` directory:

```bash
rm -rf ~/.aura/
```

## 7. Children's Privacy

AURa is a developer/research tool and is not directed at children under the
age of 13.  We do not knowingly collect personal information from children.

## 8. Changes to This Notice

This Privacy Notice may be updated.  The latest version is always in the
repository at `PRIVACY_NOTICE.md`.

## 9. Contact

Privacy questions may be submitted as a GitHub issue at
https://github.com/Cbetts1/Damn-it-xm/issues.
