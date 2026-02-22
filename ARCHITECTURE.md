# Architecture

> MCP BridgeKit v0.6 — Embeddable MCP stdio → HTTP bridge

## High-Level Overview

```mermaid
graph TB
    subgraph Clients
        WEB[Web Chatbot / Frontend]
        CLI[CLI / Script]
        API[Third-party API]
    end

    subgraph BridgeKit Server
        FP[FastAPI App<br/>app.py]
        CORE[BridgeKit Core<br/>core.py]
        DASH[Dashboard<br/>dashboard.py]
        LAND[Landing Page<br/>landing.py]
    end

    subgraph Session Pool
        S1[Session 1<br/>user-abc]
        S2[Session 2<br/>user-xyz]
        SN[Session N<br/>user-...]
    end

    subgraph MCP Servers via stdio
        MCP1[MCP Server 1<br/>analyze_data]
        MCP2[MCP Server 2<br/>search]
        MCPN[MCP Server N<br/>...]
    end

    subgraph Background Jobs
        RQ[RQ Worker<br/>worker.py]
        REDIS[(Redis)]
    end

    WEB -->|POST /chat| FP
    CLI -->|POST /chat| FP
    API -->|POST /chat| FP
    WEB -->|GET /dashboard| DASH
    WEB -->|GET /| LAND

    FP --> CORE
    CORE --> S1
    CORE --> S2
    CORE --> SN

    S1 -->|stdio| MCP1
    S2 -->|stdio| MCP2
    SN -->|stdio| MCPN

    CORE -->|timeout?<br/>enqueue job| REDIS
    REDIS --> RQ
    RQ -->|stdio| MCPN
    RQ -->|store result| REDIS
    CORE -->|poll result| REDIS

    style CORE fill:#10b981,color:#fff
    style REDIS fill:#f59e0b,color:#fff
    style FP fill:#3b82f6,color:#fff
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI (app.py)
    participant Core as BridgeKit (core.py)
    participant Pool as Session Pool
    participant MCP as MCP Server (stdio)
    participant Redis
    participant Worker as RQ Worker

    Client->>FastAPI: POST /chat {user_id, tool_name, tool_args}
    FastAPI->>Core: bridge.call(req)
    Core->>Core: _get_lock(user_id)

    alt Session exists & not expired
        Core->>Pool: Return cached session
    else New or expired
        Core->>Pool: Evict oldest if pool full
        Core->>MCP: Spawn stdio subprocess
        MCP-->>Core: read/write streams
        Core->>Pool: Store (session, stack, timestamp)
        Core->>MCP: session.list_tools()
        MCP-->>Core: Available tools
    end

    Core->>Core: asyncio.timeout(25s)
    Core->>MCP: session.call_tool(name, args)

    alt Completes within timeout
        MCP-->>Core: Tool result
        Core-->>FastAPI: SSE: data: {result}
        FastAPI-->>Client: SSE stream
    else Timeout exceeded
        Core->>Redis: SET job:{id}:status = queued
        Core->>Redis: ENQUEUE process_job
        Core-->>FastAPI: SSE: data: {status: queued, job_id}
        FastAPI-->>Client: SSE with job_id

        Note over Worker,Redis: Background execution
        Worker->>Redis: GET job payload
        Worker->>MCP: Spawn new stdio session
        Worker->>MCP: call_tool(name, args)
        MCP-->>Worker: Result
        Worker->>Redis: SET job:{id}:result
        Worker->>Redis: SET job:{id}:status = completed

        Client->>FastAPI: GET /job/{job_id}
        FastAPI->>Core: get_job_status(job_id)
        Core->>Redis: GET status + result
        Redis-->>Core: {status, result}
        Core-->>FastAPI: Job result
        FastAPI-->>Client: JSON response
    end
```

## Directory Structure

```
mcp-bridgekit/
├── src/mcp_bridgekit/          # Python package
│   ├── __init__.py             # Exports: BridgeKit, BridgeRequest, settings
│   ├── app.py                  # FastAPI app — routes, lifespan
│   ├── core.py                 # BridgeKit class — session pool, timeouts, jobs
│   ├── config.py               # pydantic-settings — env-based config
│   ├── models.py               # Pydantic request/response models
│   ├── worker.py               # RQ background worker — executes timed-out jobs
│   ├── dashboard.py            # /dashboard route — HTMX live view
│   ├── landing.py              # / route — landing page
│   └── stripe.py               # Stripe integration skeleton (commented)
├── ts/                         # TypeScript implementation
│   ├── src/index.ts            # Express server — same architecture
│   ├── package.json
│   └── tsconfig.json
├── templates/
│   └── dashboard.html          # HTMX + Tailwind dashboard template
├── examples/
│   ├── fastapi_app.py          # Embedding example
│   └── mcp_server.py           # Demo MCP server (FastMCP)
├── tests/
│   └── test_core.py            # Unit tests (mocked Redis)
├── Dockerfile
├── docker-compose.yml          # Redis + BridgeKit + Worker
├── pyproject.toml
├── .github/workflows/ci.yml    # CI: test + publish
└── .env.example
```

## Component Details

### `core.py` — BridgeKit Class

The heart of the system. Manages:

| Responsibility | Implementation |
|---|---|
| **Session pooling** | `Dict[user_id → (ClientSession, AsyncExitStack, timestamp)]` |
| **Per-user locking** | `_global_lock` protects lock-map creation; per-user `asyncio.Lock` serializes session access |
| **Pool limits** | Evicts oldest session when `max_sessions` exceeded |
| **Session TTL** | Checks `time.time() - created_at` against `session_ttl_seconds` |
| **Timeout handling** | `asyncio.timeout(threshold)` wraps `session.call_tool()` |
| **Background jobs** | On timeout: stores status in Redis, enqueues via RQ |
| **Tool discovery** | Calls `session.list_tools()` on new sessions, caches per user |
| **Logging** | Structured logging + in-memory `deque(maxlen=100)` for dashboard |

### `app.py` — API Surface

| Endpoint | Method | Purpose |
|---|---|---|
| `/chat` | POST | Call MCP tool → SSE stream (auto-queues on timeout) |
| `/job/{job_id}` | GET | Poll background job status/result |
| `/tools/{user_id}` | GET | List available MCP tools |
| `/session/{user_id}` | DELETE | Close a user's session |
| `/health` | GET | Health + active session count |
| `/dashboard` | GET | Live HTMX dashboard |
| `/dashboard/data` | GET | JSON data feed for dashboard |
| `/` | GET | Landing page |
| `/docs` | GET | Auto-generated OpenAPI docs |

### `worker.py` — Background Job Execution

```mermaid
flowchart LR
    A[RQ picks job<br/>from Redis queue] --> B[Set status: running]
    B --> C[Spawn fresh<br/>stdio MCP session]
    C --> D[call_tool<br/>name, args]
    D --> E{Success?}
    E -->|Yes| F[Store result in Redis<br/>Set status: completed]
    E -->|No| G[Store error in Redis<br/>Set status: failed]
```

Workers run in a separate process. Each job spins up its own MCP session (independent of the main server's pool) to avoid blocking the API.

### `config.py` — Settings

All settings use `MCP_BRIDGEKIT_` prefix and can be set via environment variables or `.env` file:

```mermaid
graph LR
    ENV[.env file] --> PS[pydantic-settings]
    ENVVAR[Environment Variables] --> PS
    PS --> S[Settings object]
    S --> |redis_url| REDIS[(Redis)]
    S --> |max_sessions| CORE[BridgeKit]
    S --> |timeout_threshold| CORE
    S --> |session_ttl| CORE
    S --> |job_result_ttl| WORKER[Worker]
```

## Deployment Architecture

### Docker Compose (Recommended)

```mermaid
graph TB
    subgraph Docker Network
        R[Redis<br/>redis:7-alpine<br/>:6379]
        B[BridgeKit Server<br/>python:3.12-slim<br/>:8000]
        W[RQ Worker<br/>python:3.12-slim]
    end

    INTERNET((Internet)) -->|:8000| B
    B --> R
    W --> R

    style R fill:#dc2626,color:#fff
    style B fill:#3b82f6,color:#fff
    style W fill:#8b5cf6,color:#fff
```

```bash
docker-compose up        # Starts all 3 services
```

### Manual / Bare Metal

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: API server
uvicorn mcp_bridgekit.app:app --host 0.0.0.0 --port 8000

# Terminal 3: Background worker
mcp-bridgekit-worker
```

## Data Flow — Redis Keys

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| `bridgekit:job:{id}:status` | String (JSON) | `job_result_ttl_seconds` | Job state: `queued` / `running` / `completed` / `failed` |
| `bridgekit:job:{id}:result` | String (JSON) | `job_result_ttl_seconds` | Tool call result (set by worker on completion) |
| RQ internal keys | Various | Managed by RQ | Queue metadata, job payloads |

## Concurrency Model

```mermaid
graph TD
    R1[Request user-1] --> GL[Global Lock]
    R2[Request user-1] --> GL
    R3[Request user-2] --> GL

    GL -->|create/get lock| UL1[Lock: user-1]
    GL -->|create/get lock| UL2[Lock: user-2]

    UL1 -->|serialize| S1[Session user-1]
    UL2 -->|serialize| S2[Session user-2]

    style GL fill:#ef4444,color:#fff
    style UL1 fill:#f59e0b,color:#fff
    style UL2 fill:#f59e0b,color:#fff
```

- **Global lock** (`_global_lock`): Only held briefly to look up or create per-user locks. Prevents race conditions.
- **Per-user locks**: Serialize all session operations for a single user. Different users run concurrently.
- **asyncio.timeout**: Non-blocking timeout wrapper — the event loop stays responsive.

## TypeScript Version

The `ts/` directory contains a parallel Express implementation with the same architecture:

- Same session pooling (Map-based)
- Same timeout → Redis queueing pattern
- Same API surface (`POST /chat`, `GET /health`, `DELETE /session/:userId`)

```bash
cd ts && npm install && npm run build && npm start
```
