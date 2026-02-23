"""
Example: Connecting your AWS-hosted HTTP API to MCP BridgeKit.

This shows how your existing API (running on EC2, ECS, Lambda, etc.)
calls BridgeKit to invoke MCP tools — such as AWS MCP, GitHub MCP,
filesystem MCP, or any MCP server.

Architecture:
  [Your AWS API]  ──HTTP──▶  [BridgeKit]  ──stdio──▶  [MCP Server]
  (EC2/ECS/Lambda)            (EC2/ECS)               (npx/python/binary)
"""

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ── Your existing AWS API ────────────────────────────────────

app = FastAPI(title="My AWS API")

# BridgeKit URL — wherever you deployed it
# Examples:
#   Local dev:      http://localhost:8000
#   Docker Compose: http://bridgekit:8000
#   ECS/EC2:        https://bridgekit.internal.mycompany.com
#   Vercel:         https://mcp-bridgekit.vercel.app
BRIDGEKIT_URL = "http://localhost:8000"


# ── 1. Simplest integration — call any MCP tool ─────────────

class ToolRequest(BaseModel):
    user_id: str
    query: str


@app.post("/api/analyze")
async def analyze_data(req: ToolRequest):
    """
    Your API endpoint that uses BridgeKit to call an MCP tool.
    The MCP server is configured via mcp_config.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                # ── THIS IS THE KEY: configure which MCP server to use ──
                "mcp_config": {
                    "command": "python",
                    "args": ["examples/mcp_server.py"],
                },
                "tool_name": "analyze_data",
                "tool_args": {"query": req.query},
            },
        )
        return _parse_sse(response.text)


# ── 2. Using AWS MCP Server (official @aws/aws-mcp) ─────────

@app.post("/api/aws/describe-resources")
async def aws_describe(req: ToolRequest):
    """
    Call the AWS MCP server to interact with AWS services.

    Prerequisites on the BridgeKit host:
      npm install -g @aws/aws-mcp
      (or: npx @aws/aws-mcp)

    The AWS MCP server provides tools like:
      - describe_instances
      - list_s3_buckets
      - query_cloudwatch
      - describe_stack
      etc.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "npx",
                    "args": ["-y", "@aws/aws-mcp"],
                },
                # The tool_name depends on what the AWS MCP exposes
                "tool_name": "describe_instances",
                "tool_args": {"region": "us-east-1"},
            },
        )
        return _parse_sse(response.text)


# ── 3. Using AWS CDK MCP Server ─────────────────────────────

@app.post("/api/aws/cdk-generate")
async def aws_cdk_generate(req: ToolRequest):
    """
    Call the AWS CDK MCP server for infrastructure-as-code generation.

    Prerequisites:
      npm install -g @aws/aws-cdk-mcp-server
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "npx",
                    "args": ["-y", "@aws/aws-cdk-mcp-server"],
                },
                "tool_name": "GenerateCDK",
                "tool_args": {"prompt": req.query},
            },
        )
        return _parse_sse(response.text)


# ── 4. Using AWS Documentation MCP Server ───────────────────

@app.post("/api/aws/docs")
async def aws_docs_search(req: ToolRequest):
    """
    Query AWS documentation via the AWS Docs MCP server.

    Prerequisites:
      npm install -g @aws/aws-documentation-mcp-server
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "npx",
                    "args": ["-y", "@aws/aws-documentation-mcp-server"],
                },
                "tool_name": "search_documentation",
                "tool_args": {"query": req.query},
            },
        )
        return _parse_sse(response.text)


# ── 5. Using GitHub MCP Server ──────────────────────────────

@app.post("/api/github/search")
async def github_search(req: ToolRequest):
    """
    Call the GitHub MCP server.

    Prerequisites:
      npm install -g @modelcontextprotocol/server-github
      Set GITHUB_TOKEN env var on BridgeKit host
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                },
                "tool_name": "search_repositories",
                "tool_args": {"query": req.query},
            },
        )
        return _parse_sse(response.text)


# ── 6. Using a custom Python MCP server ─────────────────────

@app.post("/api/custom-tool")
async def custom_tool(req: ToolRequest):
    """
    Call your own Python MCP server.

    Your MCP server just needs to be a Python file using FastMCP:

        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("my-tools")

        @mcp.tool()
        async def my_custom_tool(input: str) -> str:
            # ... your logic
            return result

        if __name__ == "__main__":
            mcp.run()
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "python",
                    "args": ["/path/to/your/mcp_server.py"],
                },
                "tool_name": "my_custom_tool",
                "tool_args": {"input": req.query},
            },
        )
        return _parse_sse(response.text)


# ── 7. Discover available tools from any MCP server ─────────

@app.get("/api/tools/{mcp_type}")
async def discover_tools(mcp_type: str, user_id: str = "discovery-user"):
    """
    Discover what tools an MCP server exposes.
    Call this FIRST to know which tool_name values are valid.
    """
    mcp_configs = {
        "demo": {"command": "python", "args": "examples/mcp_server.py"},
        "aws": {"command": "npx", "args": "-y,@aws/aws-mcp"},
        "aws-cdk": {"command": "npx", "args": "-y,@aws/aws-cdk-mcp-server"},
        "aws-docs": {"command": "npx", "args": "-y,@aws/aws-documentation-mcp-server"},
        "github": {"command": "npx", "args": "-y,@modelcontextprotocol/server-github"},
        "filesystem": {"command": "npx", "args": "-y,@modelcontextprotocol/server-filesystem,/tmp"},
    }

    config = mcp_configs.get(mcp_type)
    if not config:
        raise HTTPException(404, f"Unknown MCP type: {mcp_type}. Options: {list(mcp_configs)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BRIDGEKIT_URL}/tools/{user_id}",
            params={"command": config["command"], "args": config["args"]},
        )
        return resp.json()


# ── 8. Long-running tool with job polling ────────────────────

@app.post("/api/long-task")
async def long_running_task(req: ToolRequest):
    """
    For tools that take >25s, BridgeKit auto-queues them.
    This example shows the full flow: call → queued → poll → result.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Call the tool — may return immediately or queue it
        response = await client.post(
            f"{BRIDGEKIT_URL}/chat",
            json={
                "user_id": req.user_id,
                "messages": [{"role": "user", "content": req.query}],
                "mcp_config": {
                    "command": "python",
                    "args": ["examples/mcp_server.py"],
                },
                "tool_name": "analyze_data",
                "tool_args": {"query": req.query},
            },
        )

        result = _parse_sse(response.text)

        # Step 2: If it was queued, poll for completion
        if result.get("status") == "queued":
            job_id = result["job_id"]
            import asyncio

            for _ in range(60):  # poll for up to 5 minutes
                await asyncio.sleep(5)
                poll = await client.get(f"{BRIDGEKIT_URL}/job/{job_id}")
                job = poll.json()
                if job["status"] == "completed":
                    return job["result"]
                if job["status"] == "failed":
                    raise HTTPException(500, f"Job failed: {job.get('error')}")

            raise HTTPException(408, "Job timed out after 5 minutes")

        return result


# ── Helper: parse SSE response ───────────────────────────────

def _parse_sse(text: str) -> dict:
    """Extract JSON from SSE 'data: {...}' lines."""
    import json
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {"raw": text}


# ── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
