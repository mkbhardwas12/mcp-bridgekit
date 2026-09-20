# Changelog

All notable changes to MCP BridgeKit are documented here.
Contributors are credited on the change they made or reported.

## [Unreleased]

### Security
- `docker-compose.yml` binds BridgeKit to `127.0.0.1` by default (override with
  `MCP_BRIDGEKIT_BIND=0.0.0.0` when fronted by TLS / a reverse proxy) and no longer exposes Redis
  beyond the host loopback. Suggested by [@shunfeng8421](https://github.com/shunfeng8421) in
  [#3](https://github.com/mkbhardwas12/mcp-bridgekit/issues/3).
- Private vulnerability reporting enabled on the repository.

### Added
- `CONTRIBUTING.md`, issue/PR templates, Dependabot config.
- CI: lint job, Python 3.11/3.12/3.13 test matrix, PyPI trusted publishing (no stored token).
- PyPI metadata: classifiers, keywords, project URLs.

### Changed
- Version string is read from `mcp_bridgekit.__version__` everywhere (FastAPI docs, landing page).
- README: new hero, status badges, 60-second demo.

## [0.10.0] — 2026-09-20

### Security

- **Fail-closed authentication.** Protected endpoints (`/chat`, `/tools`, `/job`, `/session`)
  now return HTTP 401 `AUTH_NOT_CONFIGURED` when `MCP_BRIDGEKIT_API_KEY` is empty.
  Running without a key requires an explicit `MCP_BRIDGEKIT_ALLOW_NO_AUTH=true`.
  `docker-compose.yml` refuses to start without an API key.
  Fixes [#3](https://github.com/mkbhardwas12/mcp-bridgekit/issues/3) — reported by
  [@shunfeng8421](https://github.com/shunfeng8421) (blueQ).
- **MCP command allowlist.** `mcp_config.command` must be `DEFAULT_MCP_COMMAND` or listed in the
  new `MCP_BRIDGEKIT_ALLOWED_MCP_COMMANDS`; anything else is rejected with HTTP 400
  `COMMAND_NOT_ALLOWED` *before* any subprocess is spawned. Validation happens at the spawn
  point (`get_session`) so `/chat`, `/tools`, retries, and background-worker replays are all
  covered. `mcp_config` is now a strict model accepting only `command` and `args`.
  Fixes [#3](https://github.com/mkbhardwas12/mcp-bridgekit/issues/3).
- `GET /tools/{user_id}` no longer accepts `command`/`args` query parameters; it always uses the
  server's default MCP config.
- Timing-safe API key comparison via `hmac.compare_digest`.
  From [#1](https://github.com/mkbhardwas12/mcp-bridgekit/pull/1) by
  [@NakedoShadow](https://github.com/NakedoShadow).
- `api_key` is no longer written to the startup log.

### Fixed

- `/chat` returned HTTP 200 with an **empty body** when MCP session creation failed: the SSE
  error generator referenced the exception variable after the `except` block had unbound it
  (`NameError`). It now delivers the `SESSION_CREATE_FAILED` payload.
- SSE streams on `GET /mcp/events/{job_id}` are now closed after 10 minutes instead of staying
  open forever when a job never completes.
  From [#1](https://github.com/mkbhardwas12/mcp-bridgekit/pull/1) by
  [@NakedoShadow](https://github.com/NakedoShadow).

### Added

- `.dockerignore` (keeps `templates/` and `examples/`, which the image needs at runtime) and an
  expanded `.gitignore`. Based on [#1](https://github.com/mkbhardwas12/mcp-bridgekit/pull/1) by
  [@NakedoShadow](https://github.com/NakedoShadow).
- `SECURITY.md` with a responsible-disclosure policy.
- New error codes: `AUTH_NOT_CONFIGURED`, `COMMAND_NOT_ALLOWED`.

### Changed

- Removed unused imports flagged by `ruff` (`core.py`, `dashboard.py`, `events.py`, tests).
- README, ARCHITECTURE.md, INTEGRATION_GUIDE.md and `examples/aws_integration.py` updated for the
  new auth and allowlist behaviour.

### Not adopted from #1

- `CORSMiddleware` with `allow_origins=["*"]` **and** `allow_credentials=True`. That combination
  is insecure (and Starlette will not emit credentials for a wildcard origin). CORS should be
  configured by the embedding application or added later with an explicit origin list.

### Upgrade notes (breaking)

- Set `MCP_BRIDGEKIT_API_KEY` (e.g. `openssl rand -hex 32`) or, for trusted private networks
  only, `MCP_BRIDGEKIT_ALLOW_NO_AUTH=true`.
- If clients pass `mcp_config.command` values other than `DEFAULT_MCP_COMMAND`, add them to
  `MCP_BRIDGEKIT_ALLOWED_MCP_COMMANDS='["node", "npx"]'`.
- Replace `GET /tools/{user_id}?command=…&args=…` with `GET /tools/{user_id}`.

## [0.9.0] — earlier

- Webhook + SSE push notifications for background jobs.

## [0.8.0] — earlier

- API key auth, per-user rate limiting, retry with backoff, Prometheus metrics, structured error codes.

## [0.7.0] — earlier

- 100+ user scalability: async Redis, session health checks, gunicorn multi-worker, worker replicas.
