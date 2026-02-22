# MCP BridgeKit v0.3

**The embeddable MCP bridge that survives 30s timeouts.**

```mermaid
graph TD
    A[Your Chatbot API] --> B[BridgeKit (5 lines)]
    B --> C[stdio MCP Server]
    B --> D[Redis RQ Queue]
    D --> E[Background Worker]
    E --> F[Result via SSE / Webhook]
```

## Install
```bash
pip install -e .
# or future: pip install mcp-bridgekit
```

## Usage
```python
from fastapi import FastAPI
from mcp_bridgekit import BridgeKit, BridgeRequest

app = FastAPI()
bridge = BridgeKit()

@app.post("/chat")
async def chat(req: BridgeRequest):
    return await bridge.call(req)
```

## Run worker
```bash
mcp-bridgekit-worker
```

## Docker
```bash
docker-compose up
```

Star ⭐ if you like it!
