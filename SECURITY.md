# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | ✅ Active support |

## Reporting a Vulnerability

**Do not open a public GitHub Issue for security vulnerabilities.**

Please report security issues by emailing the maintainer directly or by using GitHub's private security advisory feature:

1. Go to the repository on GitHub
2. Click **Security** → **Advisories** → **New draft security advisory**
3. Fill in the details and submit

You will receive an acknowledgement within 48 hours. We will investigate and release a patch as soon as possible depending on severity. We will credit reporters unless they prefer to remain anonymous.

## Threat Model

AURa is a local AI virtual OS. The primary threat surface includes:

- **Shell command execution**: AURa's `ShellCommandExecutor` runs subprocesses on the host. Only run AURa in environments you control.
- **Persistence store**: The SQLite database stores key-value data. Protect `~/.aura/aura.db` with appropriate filesystem permissions.
- **HTTP server**: The virtual server binds to `0.0.0.0:8000` by default. In production, bind to `127.0.0.1` or use a reverse proxy with TLS.
- **AI backend credentials**: If using `openai_compatible` backend, `AURA_API_KEY` must be protected as an environment secret, never committed to source control.
- **Plugin system**: Only load plugins from trusted sources. Plugins execute arbitrary code inside the AURa process.

## Hardening Checklist

- [ ] Bind the server to `127.0.0.1` unless remote access is required
- [ ] Enable TLS with a valid certificate for any network-exposed deployment
- [ ] Set `AURA_API_KEY` via environment variable, never in code or config files
- [ ] Restrict `~/.aura/` directory permissions (`chmod 700 ~/.aura`)
- [ ] Review all third-party plugins before loading them
- [ ] Run AURa as a non-root user
