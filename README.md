# MCP BridgeKit

**Embeddable MCP stdio → HTTP bridge for web chatbots.**

Turn any MCP stdio server into HTTP endpoints your web app can call. Per-user session pooling, real timeout handling with background job fallback, live dashboard.

![Version](https://img.shields.io/badge/version-0.6.0-blue) [![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) ![Python](https://img.shields.io/badge/python-3.11+-blue)

---

## Table of Contents

- [What Is MCP BridgeKit?](#what-is-mcp-bridgekit)
- [The Problem It Solves](#the-problem-it-solves)
- [Use Cases & Scenarios](#use-cases--scenarios)
- [Architecture](#architecture)
- [Request Flow](#request-flow)
- [Key Features](#key-features)
- [Quickstart](#quickstart)
- [Docker (Recommended)](#docker-recommended)
- [API Reference](#api-reference)
- [Concurrency Model](#concurrency-model)
- [Configuration](#configuration)
- [Embedding in Your App](#embedding-in-your-app)
- [Project Structure](#project-structure)
- [TypeScript Version](#typescript-version)
- [Full Architecture Docs](#-full-architecture-docs)
- [License](#license)

---

## What Is MCP BridgeKit?

**MCP** (Model Context Protocol) is an open standard that lets AI applications connect to external tools and data sources. MCP servers communicate over **stdio** (stdin/stdout) — which means they run as local subprocesses and speak JSON-RPC over pipes.

**The problem**: Web applications (React, Next.js, Vue, mobile apps) can't spawn local subprocesses. They only speak HTTP. There's a protocol mismatch.

**MCP BridgeKit** is the bridge. It sits between your web app and MCP stdio servers, translating HTTP requests into stdio subprocess calls and streaming results back:

```
Your Web App  ──HTTP──▶  MCP BridgeKit  ──stdio──▶  MCP Server (tool)
                         (this project)
```

Think of it as **"nginx for MCP tools"** — a reverse proxy that makes stdio tools available over HTTP.

---

## The Problem It Solves

| Challenge | Without BridgeKit | With BridgeKit |
|-----------|-------------------|----------------|
| **Web app needs MCP tools** | Can't — browsers can't spawn subprocesses | `POST /chat` with tool name and args |
| **Multiple users sharing tools** | Each needs their own server setup | Per-user session pooling (up to 100 concurrent) |
| **Tool call takes 60 seconds** | HTTP gateway timeout (Vercel 30s, CloudFlare 30s) | Auto-queues as background job, client polls `GET /job/{id}` |
| **Which tools are available?** | Must read docs or hardcode | `GET /tools/{user_id}` — live discovery |
| **Monitoring & debugging** | Blind — no visibility | Live dashboard: sessions, jobs, logs, tools |
| **Session cleanup** | Zombie processes leak memory | Auto-eviction (TTL + pool limit) + manual `DELETE /session/{id}` |

---

## Use Cases & Scenarios

### 1. AI Chatbot with Tool Calling

> **Scenario**: You're building a customer support chatbot in React. The AI can call tools like `search_docs`, `create_ticket`, `check_order_status` — all implemented as MCP servers.

```
React App → POST /chat {tool: "search_docs", args: {query: "refund policy"}}
         ← SSE stream with search results
```

BridgeKit manages one MCP server process per conversation, so each user has isolated state.

### 2. Multi-Tenant SaaS Platform

> **Scenario**: Your SaaS lets customers connect their own MCP tools (data analysis, code generation, API integrations). Each customer uses different tools.

```
Customer A → POST /chat {user_id: "cust-A", mcp_config: {command: "python", args: ["their_tool.py"]}}
Customer B → POST /chat {user_id: "cust-B", mcp_config: {command: "node", args: ["their_tool.js"]}}
```

Each customer gets a dedicated session with their own MCP server. Pool manages up to 100 concurrent sessions with automatic eviction.

### 3. Long-Running Data Processing

> **Scenario**: An MCP tool runs complex SQL queries or ML inference that takes 45 seconds. Your frontend uses Vercel with a 30-second timeout.

```
Client → POST /chat {tool: "run_analysis", args: {dataset: "sales_2025"}}
       ← SSE: {status: "queued", job_id: "abc-123"}

# 45 seconds later...
Client → GET /job/abc-123
       ← {status: "completed", result: {revenue: 4200000, growth: "12%"}}
```

BridgeKit's `asyncio.timeout(25s)` catches the slow call, queues it via Redis/RQ, and a background worker completes it.

### 4. Internal Developer Tools

> **Scenario**: Your team has MCP tools for database queries, log analysis, and deployment — you want a single HTTP API to access all of them.

```bash
# Query production database
curl -X POST localhost:8000/chat \
  -d '{"user_id": "dev-1", "tool_name": "query_db", "tool_args": {"sql": "SELECT count(*) FROM users"}}'

# Check which tools are available
curl localhost:8000/tools/dev-1
```

Run `docker-compose up` and all your tools are accessible from any HTTP client.

### 5. Webhook / Integration Pipelines

> **Scenario**: A Slack bot, Zapier workflow, or n8n pipeline needs to call MCP tools based on triggers.

```
Slack Event → Zapier → POST /chat {tool: "summarize", args: {text: "..."}}
                     ← {result: "Here's the summary..."}
```

BridgeKit is a standard HTTP API — any integration platform can call it.

### 6. Mobile Applications

> **Scenario**: An iOS/Android app needs to call MCP tools but can't run subprocesses on the device.

```
Mobile App → POST https://your-server.com/chat
           ← SSE stream or job_id for polling
```

Deploy BridgeKit on your server, and mobile clients communicate over HTTPS.

### When NOT to Use BridgeKit

| Scenario | Better Alternative |
|----------|-------------------|
| CLI tool calling MCP servers locally | Use MCP SDK directly — no HTTP needed |
| MCP server already speaks HTTP (Streamable HTTP transport) | Connect directly — no bridge needed |
| Single-user desktop app | MCP SDK + stdio directly |

---

## Architecture

```mermaid
graph LR
    subgraph Clients
        A[🌐 Web Chatbot]
        B[⌨️ CLI / Script]
        C[🔗 Third-party API]
    end

    subgraph BridgeKit
        D[🚀 FastAPI Server\napp.py]
        E[⚡ BridgeKit Core\ncore.py]
        F[📊 Dashboard\ndashboard.py]
    end

    subgraph Backend
        G[🧠 MCP Server\nstdio process]
        H[(💾 Redis)]
        I[👷 RQ Worker\nworker.py]
    end

    A -- POST /chat --> D
    B -- POST /chat --> D
    C -- POST /chat --> D
    A -. GET /dashboard .-> F

    D --> E
    E -- stdio --> G
    G -- stdout --> E

    E -. timeout? .-> H
    H --> I
    I -- stdio --> G
    I -- store result --> H
    E -. poll result .-> H

    style E fill:#10b981,stroke:#059669,color:#fff
    style H fill:#f59e0b,stroke:#d97706,color:#fff
    style D fill:#3b82f6,stroke:#2563eb,color:#fff
    style G fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style I fill:#a855f7,stroke:#9333ea,color:#fff
```

---

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant BridgeKit as BridgeKit Core
    participant MCP as MCP Server
    participant Redis
    participant Worker as RQ Worker

    Client->>FastAPI: POST /chat {user_id, tool_name, tool_args}
    FastAPI->>BridgeKit: bridge.call(req)
    BridgeKit->>BridgeKit: Get/create session (per-user lock)
    BridgeKit->>MCP: call_tool(name, args) with asyncio.timeout(25s)

    alt ✅ Completes within timeout
        MCP-->>BridgeKit: Tool result
        BridgeKit-->>FastAPI: SSE: data: {result}
        FastAPI-->>Client: Stream response
    else ⏱ Timeout exceeded
        BridgeKit->>Redis: Enqueue job + set status=queued
        BridgeKit-->>FastAPI: SSE: {status: queued, job_id}
        FastAPI-->>Client: Return job_id
        Worker->>Redis: Pick up job
        Worker->>MCP: Spawn session + call_tool
        MCP-->>Worker: Result
        Worker->>Redis: Store result + set status=completed
        Client->>FastAPI: GET /job/{job_id}
        FastAPI->>Redis: Get status + result
        Redis-->>FastAPI: {status: completed, result: ...}
        FastAPI-->>Client: Return result
    end
```

---

## Key Features

- **Per-user sessions**: Each `user_id` gets its own MCP stdio process
- **Real timeout handling**: `asyncio.timeout()` wraps every tool call — if it exceeds the threshold, the call is automatically queued as a background job via Redis/RQ
- **Background job polling**: `GET /job/{job_id}` to check status/results
- **Tool discovery**: `GET /tools/{user_id}` lists available tools from the MCP server
- **Session management**: Auto-eviction when pool is full, TTL-based expiry, manual `DELETE /session/{user_id}`
- **Live dashboard**: HTMX + Tailwind — sessions, jobs, logs, tools (no build step)
- **Structured logging**: via structlog

## Quickstart

```bash
# Clone & install
git clone https://github.com/mkbhardwas12/mcp-bridgekit.git
cd mcp-bridgekit
pip install -e ".[dev]"

# Start Redis (required for job queue)
docker run -d -p 6379:6379 redis:7-alpine

# Run the server
uvicorn mcp_bridgekit.app:app --reload

# In another terminal — start the background worker
mcp-bridgekit-worker
```

Open http://localhost:8000 for the landing page, http://localhost:8000/dashboard for the live dashboard, http://localhost:8000/docs for API docs.

## Docker (Recommended)

```mermaid
graph TB
    subgraph Docker Compose
        R[(Redis\nredis:7-alpine\nport 6379)]
        S[BridgeKit Server\npython:3.12-slim\nport 8000]
        W[RQ Worker\npython:3.12-slim]
    end

    Internet((Internet)) -->|:8000| S
    S --> R
    W --> R

    style R fill:#ef4444,stroke:#dc2626,color:#fff
    style S fill:#3b82f6,stroke:#2563eb,color:#fff
    style W fill:#8b5cf6,stroke:#7c3aed,color:#fff
```

```bash
docker-compose up
```

This starts Redis, the BridgeKit server (port 8000), and the RQ worker.

## API Reference

### `POST /chat`
Call an MCP tool. Returns SSE stream. Auto-queues on timeout.

```json
{
  "user_id": "user-123",
  "messages": [{"role": "user", "content": "analyze sales data"}],
  "tool_name": "analyze_data",
  "tool_args": {"query": "Q4 revenue trends"},
  "mcp_config": {"command": "python", "args": ["examples/mcp_server.py"]}
}
```

### `GET /job/{job_id}`
Poll background job status. Returns `queued`, `running`, `completed` (with result), or `failed`.

### `GET /tools/{user_id}?command=python&args=examples/mcp_server.py`
List available tools from the MCP server.

### `DELETE /session/{user_id}`
Close a user's MCP session.

### `GET /health`
Health check with active session count.

## Concurrency Model

```mermaid
graph TD
    R1[Request user-abc] --> GL
    R2[Request user-abc] --> GL
    R3[Request user-xyz] --> GL

    GL[🔒 Global Lock\nheld for nanoseconds]

    GL -->|get/create| UL1[🔑 Lock: user-abc]
    GL -->|get/create| UL2[🔑 Lock: user-xyz]

    UL1 -->|serialize| S1[Session: user-abc\nMCP stdio process]
    UL2 -->|serialize| S2[Session: user-xyz\nMCP stdio process]

    S1 -->|max 100 sessions| POOL[(Session Pool\nTTL: 3600s\nEviction: oldest)]
    S2 --> POOL

    style GL fill:#ef4444,stroke:#dc2626,color:#fff
    style UL1 fill:#f59e0b,stroke:#d97706,color:#fff
    style UL2 fill:#f59e0b,stroke:#d97706,color:#fff
    style POOL fill:#10b981,stroke:#059669,color:#fff
```

## Configuration

Set via environment variables or `.env` file (prefix: `MCP_BRIDGEKIT_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `MAX_SESSIONS` | `100` | Max concurrent MCP sessions |
| `SESSION_TTL_SECONDS` | `3600` | Session expiry (1 hour) |
| `TIMEOUT_THRESHOLD_SECONDS` | `25.0` | Seconds before queuing as background job |
| `JOB_RESULT_TTL_SECONDS` | `600` | How long job results stay in Redis |
| `DEFAULT_MCP_COMMAND` | `python` | Default MCP server command |
| `DEFAULT_MCP_ARGS` | `["examples/mcp_server.py"]` | Default MCP server args |

## Embedding in Your App

```python
from fastapi import FastAPI
from mcp_bridgekit import BridgeKit, BridgeRequest

app = FastAPI()
bridge = BridgeKit()

@app.post("/chat")
async def chat(req: BridgeRequest):
    return await bridge.call(req)
```

## Project Structure

```mermaid
graph LR
    subgraph src/mcp_bridgekit
        APP[app.py\nFastAPI routes]
        CORE[core.py\nBridgeKit engine ⚡]
        CFG[config.py\npydantic-settings]
        MDL[models.py\nPydantic models]
        WRK[worker.py\nRQ worker]
        DASH[dashboard.py\n/dashboard]
        LAND[landing.py\n/ landing]
    end

    APP --> CORE
    APP --> DASH
    APP --> LAND
    CORE --> CFG
    CORE --> MDL
    WRK --> CFG

    style CORE fill:#10b981,stroke:#059669,color:#fff
    style APP fill:#3b82f6,stroke:#2563eb,color:#fff
    style WRK fill:#8b5cf6,stroke:#7c3aed,color:#fff
```

## TypeScript Version

A TypeScript implementation is available in `ts/`. Same architecture — session pooling, timeout handling, Redis queueing.

```bash
cd ts && npm install && npm run build && npm start
```

## 📐 Full Architecture Docs

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and component docs. When running the server, visit `/architecture` for an interactive HTML version.

## License

MIT
