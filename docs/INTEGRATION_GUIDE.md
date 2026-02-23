# Integration Guide: Connecting Your API to MCP Servers via BridgeKit

This guide shows how to connect **any HTTP API** (running on AWS, GCP, Vercel, or anywhere) to **any MCP server** through BridgeKit.

## How It Works

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Your HTTP API  │──HTTP──▶│   BridgeKit     │──stdio──▶│  MCP Server     │
│  (EC2/ECS/λ)    │         │  (EC2/ECS/Docker)│         │  (npx/python)   │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                     │
                                     ▼
                              ┌────────────┐
                              │   Redis    │
                              │ (ElastiCache)│
                              └────────────┘
```

**Your API** sends an HTTP POST to BridgeKit's `/chat` endpoint with:
- `user_id` — identifies the caller (for session pooling)
- `mcp_config` — which MCP server to spawn (`command` + `args`)
- `tool_name` — which tool to call
- `tool_args` — arguments for the tool

BridgeKit handles the rest: spawning the MCP process, managing sessions, timeouts, and background jobs.

---

## Step 1: Deploy BridgeKit

### Option A: Docker Compose on EC2/ECS

```bash
# On your EC2 instance or in your ECS task definition
git clone https://github.com/mkbhardwas12/mcp-bridgekit.git
cd mcp-bridgekit

# Configure
cp .env.example .env
# Edit .env — set Redis URL to your ElastiCache instance:
# MCP_BRIDGEKIT_REDIS_URL=redis://your-elasticache-endpoint:6379

docker compose up -d
# This starts: Redis + BridgeKit (4 workers) + RQ Worker (3 replicas)
```

### Option B: Standalone on EC2

```bash
pip install mcp-bridgekit   # or: uv pip install mcp-bridgekit

# Start Redis (install if needed)
sudo yum install redis       # Amazon Linux
redis-server --daemonize yes

# Start BridgeKit
export MCP_BRIDGEKIT_REDIS_URL=redis://localhost:6379
gunicorn mcp_bridgekit.app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 &

# Start background worker
mcp-bridgekit-worker &
```

### Option C: Vercel (Serverless)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fmkbhardwas12%2Fmcp-bridgekit&env=MCP_BRIDGEKIT_REDIS_URL&envDescription=Redis%20URL%20for%20session%20store%20and%20job%20queue&project-name=mcp-bridgekit)

> Note: Vercel requires an external Redis (e.g., Upstash, Redis Cloud).

---

## Step 2: Install MCP Servers on the BridgeKit Host

BridgeKit spawns MCP servers as **child processes** via stdio. You need the MCP server binaries/packages installed on the same machine where BridgeKit runs.

```bash
# AWS MCP Server (official)
npm install -g @aws/aws-mcp

# AWS CDK MCP Server
npm install -g @aws/aws-cdk-mcp-server

# AWS Documentation MCP Server
npm install -g @aws/aws-documentation-mcp-server

# GitHub MCP Server
npm install -g @modelcontextprotocol/server-github

# Filesystem MCP Server
npm install -g @modelcontextprotocol/server-filesystem

# Or use npx (downloads on first use — slower first call):
# "command": "npx", "args": ["-y", "@aws/aws-mcp"]
```

### For Python MCP servers:
```bash
pip install mcp   # or: uv pip install mcp

# Your custom server is just a Python file:
python my_mcp_server.py
```

### AWS Credentials for AWS MCP

The AWS MCP server uses standard AWS credentials. On the BridgeKit host:

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Option 2: IAM Role (best for EC2/ECS — no keys needed)
# Just attach an IAM role to your EC2 instance or ECS task

# Option 3: AWS SSO / profiles
aws sso login --profile my-profile
export AWS_PROFILE=my-profile
```

---

## Step 3: Call BridgeKit from Your API

### The Core Concept

Your API makes **one HTTP call** to BridgeKit. The `mcp_config` field tells BridgeKit which MCP server to spawn:

```python
import httpx

BRIDGEKIT_URL = "http://bridgekit.internal:8000"  # your BridgeKit deployment

async def call_mcp_tool(user_id: str, mcp_command: str, mcp_args: list,
                         tool_name: str, tool_args: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": user_id,
                "messages": [{"role": "user", "content": "request"}],
                "mcp_config": {
                    "command": mcp_command,
                    "args": mcp_args,
                },
                "tool_name": tool_name,
                "tool_args": tool_args,
            },
        )
        # Parse SSE response
        for line in response.text.strip().split("\n"):
            if line.startswith("data: "):
                return json.loads(line[6:])
```

### Calling AWS MCP

```python
# Call the AWS MCP server
result = await call_mcp_tool(
    user_id="user-123",
    mcp_command="npx",
    mcp_args=["-y", "@aws/aws-mcp"],
    tool_name="describe_instances",
    tool_args={"region": "us-east-1"},
)
```

### Calling AWS CDK MCP

```python
result = await call_mcp_tool(
    user_id="user-123",
    mcp_command="npx",
    mcp_args=["-y", "@aws/aws-cdk-mcp-server"],
    tool_name="GenerateCDK",
    tool_args={"prompt": "Create an S3 bucket with versioning"},
)
```

### Calling Your Own Python MCP Server

```python
result = await call_mcp_tool(
    user_id="user-123",
    mcp_command="python",
    mcp_args=["/app/my_tools/data_pipeline.py"],
    tool_name="run_etl",
    tool_args={"source": "s3://my-bucket/data.csv"},
)
```

---

## Step 4: Discover Available Tools

Before calling a tool, discover what's available:

```bash
# Discover tools from the demo MCP server
curl "http://bridgekit:8000/tools/discovery?command=python&args=examples/mcp_server.py"

# Discover tools from AWS MCP
curl "http://bridgekit:8000/tools/discovery?command=npx&args=-y,@aws/aws-mcp"

# Discover tools from GitHub MCP
curl "http://bridgekit:8000/tools/discovery?command=npx&args=-y,@modelcontextprotocol/server-github"
```

Response:
```json
{
  "tools": [
    {
      "name": "analyze_data",
      "description": "Analyze data with a query",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": { "type": "string" }
        },
        "required": ["query"]
      }
    }
  ]
}
```

Use the `name` from this response as your `tool_name` in subsequent `/chat` calls.

---

## Step 5: Handle Long-Running Tools

If a tool takes longer than 25 seconds (configurable), BridgeKit automatically queues it as a background job:

```python
async def call_with_polling(user_id, tool_name, tool_args, mcp_config):
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Call the tool
        resp = await client.post(f"{BRIDGEKIT_URL}/chat", json={
            "user_id": user_id,
            "messages": [{"role": "user", "content": ""}],
            "mcp_config": mcp_config,
            "tool_name": tool_name,
            "tool_args": tool_args,
        })

        result = parse_sse(resp.text)

        # 2. If completed immediately, return
        if result.get("status") != "queued":
            return result

        # 3. If queued, poll for result
        job_id = result["job_id"]
        for _ in range(60):
            await asyncio.sleep(5)
            poll = await client.get(f"{BRIDGEKIT_URL}/job/{job_id}")
            job = poll.json()
            if job["status"] == "completed":
                return job["result"]
            if job["status"] == "failed":
                raise Exception(f"Job failed: {job.get('error')}")

        raise TimeoutError("Job did not complete in 5 minutes")
```

---

## Complete Example: FastAPI on AWS + AWS MCP

Here's a full working example of an API running on AWS that uses BridgeKit to call AWS MCP tools:

```python
"""my_aws_api.py — Your API that runs on EC2/ECS/Lambda"""
import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="My AWS API")

BRIDGEKIT_URL = "http://localhost:8000"  # Change to your BridgeKit URL


class AWSRequest(BaseModel):
    user_id: str
    query: str
    region: str = "us-east-1"


def parse_sse(text: str) -> dict:
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {"raw": text}


@app.get("/api/tools")
async def list_aws_tools():
    """See what tools the AWS MCP server provides."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BRIDGEKIT_URL}/tools/aws-discovery",
            params={"command": "npx", "args": "-y,@aws/aws-mcp"},
        )
        return resp.json()


@app.post("/api/aws")
async def call_aws_tool(req: AWSRequest):
    """Call any AWS MCP tool."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "npx",
                    "args": ["-y", "@aws/aws-mcp"],
                },
                "tool_name": "describe_instances",
                "tool_args": {"region": req.region},
            },
        )

        result = parse_sse(resp.text)

        # Handle queued jobs
        if result.get("status") == "queued":
            job_id = result["job_id"]
            for _ in range(60):
                await asyncio.sleep(5)
                poll = await client.get(f"{BRIDGEKIT_URL}/job/{job_id}")
                job = poll.json()
                if job["status"] in ("completed", "failed"):
                    return job
            raise HTTPException(408, "Timeout")

        return result
```

Run it:
```bash
pip install fastapi uvicorn httpx
uvicorn my_aws_api:app --port 3000

# Test:
curl http://localhost:3000/api/tools
curl -X POST http://localhost:3000/api/aws \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-1", "query": "list my EC2 instances"}'
```

---

## MCP Server Reference

| MCP Server | Command | Args | Example Tools |
|---|---|---|---|
| **AWS MCP** | `npx` | `["-y", "@aws/aws-mcp"]` | `describe_instances`, `list_s3_buckets` |
| **AWS CDK** | `npx` | `["-y", "@aws/aws-cdk-mcp-server"]` | `GenerateCDK`, `ExplainCDK` |
| **AWS Docs** | `npx` | `["-y", "@aws/aws-documentation-mcp-server"]` | `search_documentation` |
| **GitHub** | `npx` | `["-y", "@modelcontextprotocol/server-github"]` | `search_repositories`, `create_issue` |
| **Filesystem** | `npx` | `["-y", "@modelcontextprotocol/server-filesystem", "/data"]` | `read_file`, `write_file` |
| **PostgreSQL** | `npx` | `["-y", "@modelcontextprotocol/server-postgres"]` | `query` |
| **Custom Python** | `python` | `["/path/to/server.py"]` | Whatever you define |

---

## Deployment Checklist

- [ ] BridgeKit running with Redis
- [ ] MCP server packages installed on BridgeKit host (npm or python)
- [ ] AWS credentials configured (if using AWS MCP)
- [ ] Network: Your API can reach BridgeKit over HTTP
- [ ] Network: BridgeKit can reach Redis
- [ ] Security: BridgeKit behind private VPC / API Gateway (not public)
- [ ] RQ Worker running (for background jobs)

---

## Environment Variables Reference

Set these on the **BridgeKit host** (not your API):

```bash
# BridgeKit config
MCP_BRIDGEKIT_REDIS_URL=redis://your-redis:6379
MCP_BRIDGEKIT_MAX_SESSIONS=100
MCP_BRIDGEKIT_TIMEOUT_THRESHOLD_SECONDS=25.0

# AWS credentials (for AWS MCP servers)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1

# GitHub token (for GitHub MCP server)
GITHUB_TOKEN=ghp_...
```
