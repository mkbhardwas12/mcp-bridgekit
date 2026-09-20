# Contributing to MCP BridgeKit

Thanks for helping make BridgeKit better. Small fixes, security hardening, docs and new MCP server
recipes are all welcome.

## Ground rules

- **Security first.** BridgeKit spawns subprocesses on behalf of HTTP callers. Anything that
  widens what a caller can control (commands, args, env, paths) needs an allowlist and a test.
  Found a vulnerability? Use [private reporting](https://github.com/mkbhardwas12/mcp-bridgekit/security/advisories/new), not a public issue.
- **You get credit.** Merged work is credited in [CHANGELOG.md](CHANGELOG.md) and the README, and
  your commits are preserved (or `Co-authored-by` when squashed).
- Keep PRs focused. One fix or feature per PR makes review and credit straightforward.

## Dev setup

```bash
git clone https://github.com/mkbhardwas12/mcp-bridgekit.git && cd mcp-bridgekit
uv sync --dev
cp .env.example .env && echo "MCP_BRIDGEKIT_API_KEY=$(openssl rand -hex 32)" >> .env

uv run pytest -q                       # tests run without Redis (mocked)
uv run ruff check src tests examples   # lint
uvicorn mcp_bridgekit.app:app --reload # needs Redis: docker run -d -p 6379:6379 redis:7-alpine
```

## Pull request checklist

- [ ] `uv run pytest -q` passes and new behaviour has a test
- [ ] `uv run ruff check src tests examples` is clean
- [ ] README / docs updated if config, endpoints or error codes changed
- [ ] `CHANGELOG.md` has an entry under **Unreleased** (add your handle — you earned it)
- [ ] No secrets, tokens or `.env` files committed

## Style

- Python 3.11+, type hints on public functions, `structlog` for logging.
- Prefer small pure helpers (like `validate_mcp_config`) over inline checks so they can be tested.
- Error responses carry a stable `error_code` (see `ErrorCode` in `models.py`).

## Releasing (maintainers)

1. Bump the version in `pyproject.toml` and `src/mcp_bridgekit/__init__.py`; run `uv lock`.
2. Move **Unreleased** in `CHANGELOG.md` to a dated section.
3. Tag `vX.Y.Z` and push — CI runs tests and publishes to PyPI via trusted publishing.
