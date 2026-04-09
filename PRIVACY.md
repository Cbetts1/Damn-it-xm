# Privacy Notice

**AURa — Autonomous Universal Resource Architecture**
Last updated: 2026-04-09

---

## Summary

AURa is a **local-first** system. It does not transmit your data to any server by default. All data stays on your device.

---

## Data We Collect

### When using the builtin AI backend (default)

No data leaves your device. All processing is local.

### When using the openai_compatible backend

If you configure AURa to connect to a remote API (e.g., OpenAI, Ollama hosted remotely), your queries are sent to that API. The privacy policy of that third-party provider applies. AURa does not store your API key beyond the running session.

### Telemetry

AURa collects **no telemetry**. There are no analytics calls, no crash reporting, no usage statistics sent anywhere.

---

## Data Stored Locally

AURa stores the following data locally on your device:

| Location | Contents |
|----------|----------|
| `~/.aura/aura.db` | Key-value data you store with the `store` command |
| `~/.aura/.shell_history` | AURa shell command history |
| `~/.aura/model_cache/` | Cached AI model files (if using transformers backend) |
| `~/.aura/cloud_storage/` | Files you upload to the virtual cloud |

All of this data is under your control. You can delete it at any time by removing `~/.aura/`.

---

## Third-Party Integrations

If you install third-party plugins, their privacy practices are governed by their own documentation. The AURa maintainers are not responsible for the privacy practices of third-party plugins.

---

## Children's Privacy

AURa is not directed at children under 13. We do not knowingly collect personal information from children.

---

## Contact

For privacy questions, open a GitHub Issue or contact the maintainers via the repository.
