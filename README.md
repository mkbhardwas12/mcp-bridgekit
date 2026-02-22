# MCP BridgeKit

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/mkbhardwas12/mcp-bridgekit&env=MCP_BRIDGEKIT_REDIS_URL)

**One-click deploy to Vercel** — try the dashboard instantly!

**The production-ready embeddable bridge for web chatbots + MCP stdio tools.**

Survives Vercel/Cloudflare 30s hard timeouts • Per-conversation session pooling • Background jobs • Python + TypeScript

![Version](https://img.shields.io/badge/version-0.5.0-blue) [![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) ![Stars](https://img.shields.io/github/stars/mkbhardwas12/mcp-bridgekit?style=social) ![Python](https://img.shields.io/badge/python-3.11+-blue)

## Quickstart (FastAPI)
```python
from fastapi import FastAPI
from mcp_bridgekit import BridgeKit, BridgeRequest

app = FastAPI()
bridge = BridgeKit()

@app.post("/chat")
async def chat(req: BridgeRequest):
    return await bridge.call(req)   # auto-handles short/long tools
```

## Run
```bash
pip install -e .
uvicorn mcp_bridgekit.app:app --reload
# In another terminal: mcp-bridgekit-worker
```

See `examples/` and `docker-compose up`.

## Self-Hosted Dashboard (v0.4)

Go to `http://localhost:8000/dashboard` after starting the server.

```bash
docker-compose up
# Open: http://localhost:8000/dashboard
```

Beautiful live view of sessions, jobs, logs — built with HTMX + Tailwind (no React, no build step).

Made for the MCP community. Star ⭐ if it helps!
