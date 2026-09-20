# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.10.x  | Yes       |
| < 0.10  | No — upgrade; earlier versions run without authentication by default and accept caller-supplied MCP commands ([#3](https://github.com/mkbhardwas12/mcp-bridgekit/issues/3)). |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private reporting: **Security → Report a vulnerability** on
https://github.com/mkbhardwas12/mcp-bridgekit. You should receive an acknowledgement within a few
days and a fix or mitigation plan after triage.

Reporters are credited in [CHANGELOG.md](CHANGELOG.md) and the README acknowledgements unless
they ask otherwise.

## Deployment guidance

- Always set `MCP_BRIDGEKIT_API_KEY` (e.g. `openssl rand -hex 32`). Protected endpoints are
  fail-closed and return 401 until you do.
- Only set `MCP_BRIDGEKIT_ALLOW_NO_AUTH=true` on networks you fully control.
- Keep `MCP_BRIDGEKIT_ALLOWED_MCP_COMMANDS` minimal — every entry is a binary a client can ask
  BridgeKit to spawn.
- `/health`, `/metrics`, `/dashboard`, and `/mcp/events/{job_id}` are intentionally public for
  monitoring; put BridgeKit behind a reverse proxy if you need to restrict them.
- `docker-compose.yml` binds to `127.0.0.1` by default. Set `MCP_BRIDGEKIT_BIND=0.0.0.0` only when
  BridgeKit sits behind TLS and a reverse proxy.
