# MCP BridgeKit

**The production-ready embeddable bridge for web chatbots + MCP stdio tools.**

Survives Vercel/Cloudflare 30s hard timeouts • Per-conversation session pooling • Background jobs • Python + TypeScript

![Version](https://img.shields.io/badge/version-0.3.1-blue) [![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

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

Made for the MCP community. Star ⭐ if it helps!
